"""Fresh enrollment, truthful failures and recovery using synthetic app profiles."""
import copy
import contextlib
import ctypes.util
import json
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import types
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import integrations as integration
import integration_apps as apps
import gdm_admin


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


class Enrollment(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.running = []
        self.commands = []
        self.flatpaks = set()
        self.native = {'unopkg'}
        self.c = integration.Context(self.home, runner=self.command, processes=lambda names: self.running)
        self.c.flatpak = lambda name: name in self.flatpaks
        self.c.native = lambda name, candidates=(): '/fake/' + name if name in self.native else None
        self.c.root = ROOT / 'src'
        self.which = patch.object(apps.shutil, 'which', side_effect=lambda name: '/fake/unopkg' if name == 'unopkg' else None)
        self.which.start()
        self.addCleanup(self.which.stop)
        self.artifacts = {}
        values = {
            '.cache/noctalia/zen-browser/zen-userChrome.css': '/* zen chrome */',
            '.cache/noctalia/zen-browser/zen-userContent.css': '/* zen content */',
            '.local/state/project-largo/rendered/obsidian.css': '/* obsidian */',
            '.local/state/noctalia/application-themes/zotero.css': '/* zotero */',
            '.local/state/omarchy/current/theme/zotero-pdf-theme.json': '{"background":"#202724","foreground":"#ede0b7"}',
            '.local/state/noctalia/libreoffice-theme-staging/Theme_Colors.xcu': '<colors><value>91ad85</value></colors>',
            '.local/share/themes/Noctalia-LibreOffice/gtk-3.0/gtk.css': '/* GTK */',
            '.local/share/themes/Noctalia-LibreOffice/gtk-3.0/gtk-dark.css': '/* GTK dark */',
        }
        for name, value in values.items():
            self.artifacts[self.home / name] = value.encode()
        self.office_targets = {}
        self.fail_backend = None
        self.fake_success = False
        toolkit = patch.object(apps.LibreOffice, 'verify_toolkit', return_value=None)
        toolkit.start()
        self.addCleanup(toolkit.stop)

    def command(self, args):
        args = list(map(str, args))
        self.commands.append(args)
        if '--command=sh' in args:
            return '/app/bin/unopkg\n' if 'command -v unopkg' in args[-1] else '/sandbox/data' if '$XDG_DATA_HOME' in args[-1] else '/sandbox/config'
        backend = 'flatpak' if args[0] == 'flatpak' else 'native'
        target = self.office_targets[backend]
        if 'list' in args:
            self.assertNotIn(apps.OFFICE_ID, args, 'Listing a missing specific ID fails on real unopkg')
            return 'Identifier: ' + apps.OFFICE_ID + '\n' if (target / 'uno_packages/cache/uno_packages.pmap').exists() else ''
        if 'remove' in args:
            shutil.rmtree(target / 'uno_packages', ignore_errors=True)
            return ''
        if 'add' in args:
            if backend == self.fail_backend:
                raise subprocess.CalledProcessError(1, args, stderr='deliberate sandbox install failure')
            if self.fake_success:
                return ''
            base = target / 'uno_packages/cache'
            package = base / 'uno_packages/test.tmp_/noctalia-theme.oxt'
            package.mkdir(parents=True, exist_ok=True)
            package_path = args[-1]
            if backend == 'flatpak':
                package_path = str(self.home / '.var/app/org.libreoffice.LibreOffice/data' / Path(package_path).relative_to('/sandbox/data'))
            with zipfile.ZipFile(package_path) as archive:
                for name in ('Theme_Colors.xcu', 'description.xml'):
                    put(package / name, archive.read(name))
            put(base / 'uno_packages.pmap', apps.OFFICE_ID)
            put(base / 'registry/com.sun.star.comp.deployment.bundle.PackageRegistryBackend/backenddb.xml',
                '<extensions><extension url="vnd.sun.star.expand:$UNO_USER_PACKAGES_CACHE/uno_packages/test.tmp_/noctalia-theme.oxt"/></extensions>')
            put(base / 'registry/com.sun.star.comp.deployment.configuration.PackageRegistryBackend/backenddb.xml',
                '<configurations><configuration url="vnd.sun.star.expand:$UNO_USER_PACKAGES_CACHE/uno_packages/test.tmp_/noctalia-theme.oxt/Theme_Colors.xcu"/></configurations>')
            return ''
        raise AssertionError('Unexpected command: ' + repr(args))

    def run_adapter(self, app, action='setup', palette='oma Largo', **kwargs):
        return integration.execute(self.c, action, app, artifacts=self.artifacts, palette=palette, **kwargs)

    def obsidian(self):
        self.native.add('obsidian')
        vault = self.home / 'Vault'
        directory = vault / '.obsidian'
        directory.mkdir(parents=True)
        put(vault / 'Personal.md', 'PRIVATE NOTE: never access')
        put(self.home / '.config/obsidian/obsidian.json', json.dumps({'vaults': {'one': {'path': str(vault)}}}))
        put(directory / 'appearance.json', '{"enabledCssSnippets":["other"],"fontSize":17,"cssTheme":"User theme"}\n')
        return directory

    def browser(self, name='zen'):
        self.native.add(name)
        base = self.home / ('.zen' if name == 'zen' else '.zotero/zotero')
        profile = base / 'fresh.default'
        profile.mkdir(parents=True)
        put(base / 'profiles.ini', '[Profile0]\nPath=fresh.default\nIsRelative=1\n')
        if name == 'zen':
            if not ctypes.util.find_library('lz4'):
                self.skipTest('liblz4 required for native Zen session format fixture')
            self.session = dict(spaces=[dict(uuid='space-1', theme=dict(type='gradient', gradientColors=[{'c': '#123456'}],
                                opacity=0.7, texture=0.2, rotation=-30), layout='browser-owned')],
                                windows=[{'tabs': [{'url': 'https://fixture.invalid/private'}]}])
            put(profile / 'zen-sessions.jsonlz4', apps.pack_session(self.session))
        return profile

    def office(self, backend):
        base = '.config/libreoffice/4/user' if backend == 'native' else '.var/app/org.libreoffice.LibreOffice/config/libreoffice/4/user'
        profile = self.home / base
        put(profile / 'registrymodifications.xcu', '<oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/unrelated"><prop oor:name="Keep"><value>unchanged</value></prop></item></oor:items>')
        self.office_targets[backend] = profile
        source = self.home / '.local/state/noctalia/community-templates/libreoffice'
        source.mkdir(parents=True, exist_ok=True)
        for name in ('Paths.xcu', 'description.xml', 'pkg-description.en'):
            shutil.copyfile(ROOT / 'assets/community/libreoffice' / name, source / name)
        launcher = 'libreoffice-startcenter.desktop' if backend == 'native' else 'org.libreoffice.LibreOffice.desktop'
        command = 'libreoffice --writer %U' if backend == 'native' else '/usr/bin/flatpak run org.libreoffice.LibreOffice %U'
        put(self.home / '.local/share/applications' / launcher,
            '[Desktop Entry]\nType=Application\nName=Office\nExec=' + command + '\nMimeType=test/keep;\nIcon=office\n')
        if backend == 'flatpak':
            self.flatpaks.add('org.libreoffice.LibreOffice')
        return profile

    def test_missing_optional_apps_and_read_only_status(self):
        report = self.run_adapter('obsidian', 'status')
        self.assertTrue(all(r['state'] == 'Not installed' for r in report['results']))
        self.assertFalse(report['failed'])
        self.assertFalse(self.c.state.exists())
        self.assertEqual(self.commands, [])

    def test_later_install_enables_registered_vault_without_note_access(self):
        self.run_adapter('obsidian')
        directory = self.obsidian()
        real_read_bytes, real_read_text = Path.read_bytes, Path.read_text
        def guarded_bytes(path):
            self.assertNotEqual(path.suffix, '.md', 'personal note read')
            return real_read_bytes(path)
        def guarded_text(path, *args, **kwargs):
            self.assertNotEqual(path.suffix, '.md', 'personal note read')
            return real_read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_bytes', guarded_bytes), patch.object(Path, 'read_text', guarded_text):
            report = self.run_adapter('obsidian')
        self.assertFalse(report['failed'], report)
        data = json.loads((directory / 'appearance.json').read_text())
        self.assertEqual(data['enabledCssSnippets'], ['other', 'noctalia'])
        self.assertEqual(data['fontSize'], 17)
        self.assertEqual(data['cssTheme'], 'User theme')

    def test_repeat_setup_repairs_hook_without_duplicates(self):
        directory = self.obsidian()
        first = self.run_adapter('obsidian')
        count = len(list((self.c.state / 'operations').iterdir()))
        self.run_adapter('obsidian')
        self.assertEqual(len(list((self.c.state / 'operations').iterdir())), count)
        (directory / 'snippets/noctalia.css').unlink()
        self.run_adapter('obsidian', 'repair')
        self.assertEqual(json.loads((directory / 'appearance.json').read_text())['enabledCssSnippets'].count('noctalia'), 1)
        self.assertTrue((directory / 'snippets/noctalia.css').exists())
        self.assertEqual(first['results'][0]['state'], 'Restart required')

    def test_restore_preserves_unrelated_json_edits(self):
        directory = self.obsidian()
        first = self.run_adapter('obsidian')['results'][0]
        path = directory / 'appearance.json'
        data = json.loads(path.read_text())
        data['fontSize'] = 25
        data['enabledCssSnippets'].append('later')
        path.write_text(json.dumps(data))
        integration.restore(self.c, first['operation'])
        data = json.loads(path.read_text())
        self.assertEqual(data['fontSize'], 25)
        self.assertEqual(data['enabledCssSnippets'], ['other', 'later'])
        self.assertFalse((directory / 'snippets/noctalia.css').exists())

    def test_stale_app_profile_is_not_enrolled_after_uninstall(self):
        directory = self.obsidian()
        self.native.remove('obsidian')
        before = (directory / 'appearance.json').read_bytes()
        report = self.run_adapter('obsidian')
        self.assertTrue(all(row['state'] == 'Not installed' for row in report['results']))
        self.assertEqual((directory / 'appearance.json').read_bytes(), before)

    def test_flatpak_vault_registration_is_supported(self):
        directory = self.obsidian()
        native_registry = self.home / '.config/obsidian/obsidian.json'
        put(self.home / '.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json', native_registry.read_bytes())
        self.native.remove('obsidian')
        self.flatpaks.add('md.obsidian.Obsidian')
        report = self.run_adapter('obsidian')
        self.assertEqual(report['results'][1]['state'], 'Restart required')
        self.assertIn('noctalia', json.loads((directory / 'appearance.json').read_text())['enabledCssSnippets'])

    def test_restore_refuses_later_owned_file_edits(self):
        directory = self.obsidian()
        first = self.run_adapter('obsidian')['results'][0]
        path = directory / 'snippets/noctalia.css'
        path.write_text('/* user changed owned snippet */')
        with self.assertRaisesRegex(ValueError, 'Later edit'):
            integration.restore(self.c, first['operation'])
        self.assertIn('user changed', path.read_text())

    def test_running_app_defers_profile_changes(self):
        directory = self.obsidian()
        before = (directory / 'appearance.json').read_bytes()
        self.running = ['123:456']
        report = self.run_adapter('obsidian')
        self.assertEqual(report['results'][0]['state'], 'Close app and retry')
        self.assertEqual((directory / 'appearance.json').read_bytes(), before)
        self.assertFalse((directory / 'snippets').exists())

    def test_dry_run_does_not_change_profile_or_create_backup(self):
        directory = self.obsidian()
        before = (directory / 'appearance.json').read_bytes()
        report = self.run_adapter('obsidian', dry_run=True)
        self.assertEqual(report['results'][0]['state'], 'Setup needed')
        self.assertEqual((directory / 'appearance.json').read_bytes(), before)
        self.assertFalse(self.c.state.exists())

    def test_vanilla_and_custom_are_reversible_for_vault_settings(self):
        directory = self.obsidian()
        self.run_adapter('obsidian')
        self.run_adapter('obsidian', palette='Vanilla Gnome')
        data = json.loads((directory / 'appearance.json').read_text())
        self.assertNotIn('noctalia', data['enabledCssSnippets'])
        self.assertNotIn('cssTheme', data)
        self.run_adapter('obsidian', palette='Vanilla Gnome Dark')
        self.assertEqual(json.loads((directory / 'appearance.json').read_text())['theme'], 'obsidian')
        result = self.run_adapter('obsidian')
        self.assertFalse(result['failed'], result)
        data = json.loads((directory / 'appearance.json').read_text())
        self.assertEqual(data['cssTheme'], 'User theme')
        self.assertIn('noctalia', data['enabledCssSnippets'])

    def test_bad_vault_does_not_stop_other_vaults(self):
        directory = self.obsidian()
        second = self.home / 'Second/.obsidian'
        second.mkdir(parents=True)
        registry = self.home / '.config/obsidian/obsidian.json'
        data = json.loads(registry.read_text())
        data['vaults']['second'] = {'path': str(second.parent)}
        registry.write_text(json.dumps(data))
        (directory / 'appearance.json').write_text('{broken')
        report = self.run_adapter('obsidian')
        self.assertTrue(report['failed'])
        self.assertTrue((second / 'snippets/noctalia.css').exists())

    def test_zen_enrollment_preserves_layout_and_native_gradient_properties(self):
        profile = self.browser()
        put(profile / 'chrome/userChrome.css', '/* user CSS */\n')
        report = self.run_adapter('zen')
        self.assertFalse(report['failed'], report)
        current = apps.unpack_session((profile / 'zen-sessions.jsonlz4').read_bytes())
        self.assertEqual(current['windows'], self.session['windows'])
        self.assertEqual(current['spaces'][0]['layout'], 'browser-owned')
        theme = current['spaces'][0]['theme']
        self.assertEqual(theme['rotation'], -30)
        self.assertEqual(theme['opacity'], 0.7)
        self.assertEqual(theme['gradientColors'], apps.gradient())
        self.run_adapter('zen')
        text = (profile / 'chrome/userChrome.css').read_text()
        self.assertEqual(text.count('@import'), 1)
        self.assertIn('user CSS', text)
        self.assertEqual((profile / 'user.js').read_text().count('user_pref('), 1)

    def test_zen_restore_preserves_later_tabs(self):
        profile = self.browser()
        outcome = self.run_adapter('zen')['results'][0]
        path = profile / 'zen-sessions.jsonlz4'
        data = apps.unpack_session(path.read_bytes())
        data['windows'][0]['tabs'].append({'url': 'https://fixture.invalid/later'})
        path.write_bytes(apps.pack_session(data))
        integration.restore(self.c, outcome['operation'])
        restored = apps.unpack_session(path.read_bytes())
        self.assertEqual(restored['spaces'], self.session['spaces'])
        self.assertEqual(len(restored['windows'][0]['tabs']), 2)

    def test_css_import_adopts_legacy_alias_and_ignores_comments(self):
        profile = self.browser()
        path = profile / 'chrome/userChrome.css'
        alias = self.home / '.cache/noctalia/zen-browser/zen-userChrome.css'
        owned = profile / 'chrome/noctalia/zen-userChrome.css'
        text = f'/* @import url("noctalia/zen-userChrome.css"); */\n@import url("{alias.as_uri()}");\n@import url(noctalia/zen-userChrome.css);\n/* other CSS */'
        updated = apps.css_import(text, path, owned, [alias])
        self.assertEqual(updated.count('@import'), 2)  # one comment and one active import
        self.assertNotIn(alias.as_uri(), updated)
        self.assertIn('other CSS', updated)
        self.assertEqual(apps.css_import(updated, path, owned, [alias]), updated)

    def test_profile_symlinks_do_not_escape_obsidian_configuration(self):
        directory = self.obsidian()
        outside = self.home / 'Personal'
        outside.mkdir()
        (directory / 'snippets').symlink_to(outside)
        report = self.run_adapter('obsidian')
        self.assertTrue(report['failed'])
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_snippet_never_reads_or_modifies_note_target(self):
        directory = self.obsidian()
        note = directory.parent / 'Personal.md'
        (directory / 'snippets').mkdir()
        (directory / 'snippets/noctalia.css').symlink_to(note)
        original_read = Path.read_bytes
        def no_notes(path):
            self.assertNotEqual(path, note)
            return original_read(path)
        with patch.object(Path, 'read_bytes', no_notes):
            report = self.run_adapter('obsidian')
        self.assertTrue(report['failed'])
        self.assertEqual(note.read_text(), 'PRIVATE NOTE: never access')

    def test_zen_unknown_session_fails_without_any_profile_changes(self):
        profile = self.browser()
        put(profile / 'zen-sessions.jsonlz4', b'unknown format')
        report = self.run_adapter('zen')
        self.assertTrue(report['failed'])
        self.assertFalse((profile / 'chrome').exists())

    def test_zen_initial_unstyled_workspace_can_be_enrolled_and_restored(self):
        profile = self.browser()
        for initial in (None, 'missing'):
            with self.subTest(initial=initial):
                data = copy.deepcopy(self.session)
                if initial == 'missing':
                    data['spaces'][0].pop('theme')
                else:
                    data['spaces'][0]['theme'] = None
                path = profile / 'zen-sessions.jsonlz4'
                path.write_bytes(apps.pack_session(data))
                report = self.run_adapter('zen')
                self.assertFalse(report['failed'], report)
                self.assertEqual(apps.unpack_session(path.read_bytes())['spaces'][0]['theme']['gradientColors'], apps.gradient())
                integration.restore(self.c, report['results'][0]['operation'])
                self.assertEqual(apps.unpack_session(path.read_bytes()), data)

    def test_open_app_once_is_distinct_from_absent(self):
        self.flatpaks.add('app.zen_browser.zen')
        report = self.run_adapter('zen')
        self.assertEqual(report['results'][1]['state'], 'Open app once')

    def test_ordinary_switch_updates_enrolled_css_without_profile_writes(self):
        directory = self.obsidian()
        self.run_adapter('obsidian')
        for path, value in self.artifacts.items():
            put(path, value.replace(b'obsidian', b'new palette'))
        before = (directory / 'appearance.json').read_bytes()
        self.running = ['123:456']
        report = integration.execute(self.c, 'apply', app='obsidian', palette='oma Nord', enrolled_only=True)
        self.assertEqual((directory / 'appearance.json').read_bytes(), before)
        self.assertIn(b'new palette', (directory / 'snippets/noctalia.css').read_bytes())
        self.assertEqual(report['results'][0]['state'], 'Restart required')

    def test_ordinary_switch_updates_closed_enrolled_app_without_setup(self):
        directory = self.obsidian()
        self.run_adapter('obsidian')
        for path, value in self.artifacts.items():
            put(path, value.replace(b'obsidian', b'next palette'))
        report = integration.execute(self.c, 'apply', app='obsidian', palette='oma Nord', enrolled_only=True)
        self.assertFalse(report['failed'], report)
        self.assertIn(b'next palette', (directory / 'snippets/noctalia.css').read_bytes())
        self.assertEqual(report['results'][0]['state'], 'Restart required')
        self.assertEqual(self.c.registry()['obsidian:native:' + str(directory)]['palette'], 'oma Nord')

    def test_zotero_bridge_is_packaged_and_requires_activation(self):
        profile = self.browser('zotero')
        report = self.run_adapter('zotero')
        self.assertFalse(report['failed'], report)
        self.assertEqual(report['results'][0]['state'], 'Restart required')
        with zipfile.ZipFile(profile / f'extensions/{apps.PDF_ID}.xpi') as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['applications']['zotero']['id'], apps.PDF_ID)
            self.assertIn(b'function startup()', archive.read('bootstrap.js'))
        self.assertEqual((profile / 'chrome/userContent.css').read_text().count('@import'), 1)

    def test_zotero_flatpak_is_not_enrolled(self):
        self.flatpaks.add('org.zotero.Zotero')
        flatpak = self.home / '.var/app/org.zotero.Zotero'
        flatpak.mkdir(parents=True)
        report = self.run_adapter('zotero')
        self.assertTrue(all(r['state'] == 'Not installed' for r in report['results']))
        self.assertEqual(list(flatpak.iterdir()), [])

    def test_native_and_flatpak_office_install_and_verify(self):
        native, flatpak = self.office('native'), self.office('flatpak')
        report = self.run_adapter('libreoffice')
        self.assertFalse(report['failed'], report)
        self.assertTrue(all(r['state'] == 'Restart required' for r in report['results']))
        self.assertTrue(any('--command=/app/bin/unopkg' in command for command in self.commands))
        self.assertFalse(any('/app/libreoffice/program/unopkg' in ' '.join(command) and '--command=sh' not in command for command in self.commands))
        for profile in (native, flatpak):
            self.assertIn(b'<value>Noctalia</value>', (profile / 'registrymodifications.xcu').read_bytes())
            self.assertIn(b'unchanged', (profile / 'registrymodifications.xcu').read_bytes())
        count = sum('add' in command for command in self.commands)
        self.run_adapter('libreoffice')
        self.assertEqual(sum('add' in command for command in self.commands), count)

    def test_office_partial_failure_is_not_hidden_or_cached(self):
        self.office('native')
        flatpak = self.office('flatpak')
        before = (flatpak / 'registrymodifications.xcu').read_bytes()
        self.fail_backend = 'flatpak'
        report = self.run_adapter('libreoffice')
        self.assertTrue(report['failed'])
        self.assertEqual(report['results'][0]['state'], 'Restart required')
        self.assertEqual(report['results'][1]['state'], 'Failed')
        self.assertEqual((flatpak / 'registrymodifications.xcu').read_bytes(), before)
        self.fail_backend = None
        report = self.run_adapter('libreoffice')
        self.assertFalse(report['failed'], report)
        self.assertTrue(apps.LibreOffice(self.c).extension_matches(apps.LibreOffice(self.c).discover()[1], apps.LibreOffice(self.c).office_colors(self.artifacts)))

    def test_office_success_exit_without_registration_is_failure(self):
        self.office('native')
        self.fake_success = True
        report = self.run_adapter('libreoffice')
        self.assertTrue(report['failed'])
        self.assertIn('did not verify', report['results'][0]['detail'])
        self.assertNotIn('libreoffice:native:', json.dumps(self.c.registry()))

    def test_office_status_does_not_run_unopkg(self):
        self.office('native')
        self.run_adapter('libreoffice')
        self.commands.clear()
        self.run_adapter('libreoffice', 'status')
        self.assertEqual(self.commands, [])

    def test_native_office_without_unopkg_is_not_reported_absent(self):
        profile = self.office('native')
        self.native.remove('unopkg')
        self.native.add('libreoffice')
        before = (profile / 'registrymodifications.xcu').read_bytes()
        report = self.run_adapter('libreoffice')
        self.assertEqual(report['results'][0]['state'], 'Administrator setup required')
        self.assertEqual((profile / 'registrymodifications.xcu').read_bytes(), before)

    def test_office_restore_preserves_later_unrelated_settings(self):
        profile = self.office('native')
        row = self.run_adapter('libreoffice')['results'][0]
        path = profile / 'registrymodifications.xcu'
        path.write_text(path.read_text().replace('unchanged', 'later user setting'))
        integration.restore(self.c, row['operation'])
        self.assertIn('later user setting', path.read_text())
        self.assertNotIn('CurrentColorScheme', path.read_text())

    def test_office_launch_route_preserves_arguments_and_vanilla_environment(self):
        profile = self.office('native')
        target = next(t for t in apps.LibreOffice(self.c).discover() if t['backend'] == 'native')
        changes = apps.LibreOffice(self.c).launcher(target, 'oma Largo')
        wrapper, source, _ = next(v for v in changes if v[0].name == 'project-largo-office')
        put(wrapper, source)
        state = self.home / '.local/state/oma-theme/gnome.json'
        code = 'import json,os,sys; print(json.dumps([os.environ.get("SAL_USE_VCLPLUGIN"),os.environ.get("GTK_THEME"),sys.argv[1:]]))'
        env = dict(os.environ, HOME=str(self.home))
        put(state, '{"palette":"oma Largo"}')
        command = [sys.executable, str(wrapper), 'native', '/usr/bin/env', 'SAL_USE_VCLPLUGIN=kf6',
                   'GTK_THEME=Old', sys.executable, '-c', code, 'file with spaces.odt', 'GTK_THEME=document.odt']
        output = json.loads(subprocess.run(command, env=env, check=True, capture_output=True, text=True).stdout)
        self.assertEqual(output, ['gtk3', 'Noctalia-LibreOffice', ['file with spaces.odt', 'GTK_THEME=document.odt']])
        put(state, '{"palette":"Vanilla Gnome Dark"}')
        output = json.loads(subprocess.run(command, env=env, check=True, capture_output=True, text=True).stdout)
        self.assertEqual(output[:2], ['gtk3', None])
        spy = put(self.home / 'bin/flatpak', '#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
        spy.chmod(0o755)
        output = json.loads(subprocess.run([sys.executable, str(wrapper), 'flatpak', str(spy), 'run',
            '--env=SAL_USE_VCLPLUGIN=kf6', '--env=GTK_THEME=Old', '--branch=master',
            'org.libreoffice.LibreOffice', '--env=GTK_THEME=document', 'file with spaces.odt'],
            env=env, check=True, capture_output=True, text=True).stdout)
        self.assertEqual(output, ['run', '--env=SAL_USE_VCLPLUGIN=gtk3', '--env=GTK_THEME=', '--branch=master',
                                 'org.libreoffice.LibreOffice', '--env=GTK_THEME=document', 'file with spaces.odt'])

    def test_fresh_process_observation_distinguishes_ready_from_restart(self):
        self.obsidian()
        self.run_adapter('obsidian')
        self.running = ['123:456']
        self.c.started_after = lambda names, timestamp: True
        row = self.run_adapter('obsidian', 'status')['results'][0]
        self.assertEqual(row['state'], 'Ready')
        self.assertEqual(self.run_adapter('obsidian')['results'][0]['state'], 'Close app and retry')

    def test_cli_setup_status_and_restore_share_backend(self):
        directory = self.obsidian()
        engine = types.SimpleNamespace(HOME=self.home, STATE=self.home / '.local/state/oma-theme',
            selection=lambda: {'palette': 'oma Largo'},
            stage_integrations=lambda name, path: (self.artifacts, {}))
        with patch.object(integration, 'Context', return_value=self.c):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = integration.main(['setup', '--app', 'obsidian', '--json'], engine)
            self.assertEqual(code, 0)
            report = json.loads(output.getvalue())
            operation = report['results'][0]['operation']
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(integration.main(['status', '--app', 'obsidian', '--json'], engine), 0)
                self.assertEqual(integration.main(['restore', operation], engine), 0)
        self.assertNotIn('noctalia', json.loads((directory / 'appearance.json').read_text())['enabledCssSnippets'])

    def test_application_locks_block_even_when_process_identity_is_unavailable(self):
        directory = self.obsidian()
        lock = self.home / '.config/obsidian/SingletonLock'
        lock.symlink_to('host-12345')
        report = self.run_adapter('obsidian')
        self.assertEqual(report['results'][0]['state'], 'Close app and retry')
        self.assertFalse((directory / 'snippets').exists())

    def test_concurrent_change_is_preserved(self):
        path = put(self.home / 'settings', 'before')
        calls = []
        def guard():
            calls.append(True)
            if len(calls) == 2:
                path.write_text('concurrent user edit')
        tx = integration.Transaction(self.c, 'test', guard)
        with self.assertRaisesRegex(ValueError, 'changed during enrollment'):
            tx.write(path, b'ours')
        self.assertEqual(path.read_text(), 'concurrent user edit')

    def test_all_requested_status_labels_are_explicit(self):
        self.assertEqual(set(integration.STATES), {'Ready', 'Not installed', 'Setup needed', 'Open app once',
            'Restart required', 'Close app and retry', 'Administrator setup required', 'Failed'})


class GDMContracts(unittest.TestCase):
    def test_administrator_install_and_restore_in_synthetic_system_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            home = base / 'home/newuser'
            account = types.SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid())
            files = gdm_admin.setup_files(account, b'publisher')
            mapped = {base / 'system' / path.relative_to('/'): value for path, value in files.items()}
            helper = base / 'system/usr/local/libexec/project-largo-gdm'
            config = base / 'system/etc/project-largo-gdm.json'
            target = base / 'system/usr/local/share/project-largo/gdm'
            backup = base / 'backup'
            put(helper, b'previous root helper')
            put(target / 'generation-original/gnome-shell-dark.css', 'old greeter')
            (target / 'current').symlink_to('generation-original')
            put(home / '.local/state/project-largo/gdm/request.json', json.dumps(
                dict(version=1, vanilla=True, light=True, palette='Vanilla Gnome')))
            calls = []
            def command(*args, **kwargs):
                calls.append(args)
                if '--version' in args:
                    return 'GNOME Shell 50.6'
                return '/* exact stock */' if 'extract' in args else ''
            with patch.multiple(gdm_admin, CONFIG=config, HELPER=helper, TARGET=target, BACKUP=backup), \
                 patch.object(gdm_admin, 'setup_files', return_value=mapped), \
                 patch.object(gdm_admin, 'gdm_available', return_value=True), \
                 patch.object(gdm_admin.pwd, 'getpwnam', return_value=account), \
                 patch.object(gdm_admin.pwd, 'getpwuid', return_value=account), \
                 patch.object(gdm_admin, 'command', side_effect=command), \
                 patch.object(gdm_admin.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'disabled\n', '')), \
                 contextlib.redirect_stdout(io.StringIO()):
                gdm_admin.setup('newuser')
                operation = next(backup.iterdir()).name
                self.assertEqual(helper.read_bytes(), b'publisher')
                self.assertEqual((target / 'current/gnome-shell-dark.css').read_text(), '/* exact stock */')
                gdm_admin.restore(operation)
            self.assertEqual(helper.read_bytes(), b'previous root helper')
            self.assertEqual(os.readlink(target / 'current'), 'generation-original')
            self.assertFalse(config.exists())
            self.assertFalse(any('restart' in command for command in calls))

    def test_setup_plan_is_account_bound_and_gdm_only(self):
        import types
        account = types.SimpleNamespace(pw_dir='/home/newuser', pw_uid=1005)
        files = gdm_admin.setup_files(account, b'root helper source')
        service = files[Path('/etc/systemd/system/project-largo-gdm.service')]
        overlay = files[Path('/etc/systemd/user/org.gnome.Shell@gdm.service.d/50-project-largo.conf')]
        self.assertIn(b'/home/newuser/', service)
        self.assertIn(b'python3 -I /usr/local/libexec/project-largo-gdm publish', service)
        self.assertIn(b'G_RESOURCE_OVERLAYS=', overlay)
        self.assertNotIn(b'Restart=', service)
        self.assertEqual(json.loads(files[gdm_admin.CONFIG])['uid'], 1005)

    def test_request_validation_and_stock_fallback(self):
        valid = dict(version=1, vanilla=True, light=False, palette='Vanilla Gnome Dark')
        gdm_admin.validate(valid)
        for change in ({'vanilla': 'true'}, {'wallpaper': '../image'}, {'vanilla': False, 'tokens': {}}):
            with self.assertRaises(ValueError):
                gdm_admin.validate({**valid, **change})
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            def command(*args):
                return 'GNOME Shell 51.0' if '--version' in args else '/* exact stock CSS */'
            with patch.object(gdm_admin, 'command', side_effect=command):
                gdm_admin.render(dict(version=1, vanilla=False, palette='oma Fixture',
                                      tokens={key: '#112233' for key in gdm_admin.KEYS}), directory)
            self.assertEqual((directory / 'gnome-shell-dark.css').read_text(), '/* exact stock CSS */')

    def test_request_reader_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            put(directory / 'real', '{}')
            (directory / 'request.json').symlink_to('real')
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with self.assertRaises(OSError):
                    gdm_admin.read_request_file(fd, 'request.json', 65536, os.getuid())
            finally:
                os.close(fd)


if __name__ == '__main__':
    unittest.main()
