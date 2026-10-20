#!/usr/bin/python3
"""A native, single-instance GNOME picker for the shared Oma palettes."""
import json
from pathlib import Path
import subprocess
import threading
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk
import engine


class PalettePicker(Adw.Application):
    def __init__(self):
        Gtk.init()
        # This app uses the supported GNOME color-scheme preference through libadwaita.
        Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', False)
        super().__init__(application_id='io.github.buff.OmaThemes', flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.window = Adw.ApplicationWindow(application=self, title='Project Largo', default_width=640, default_height=720)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        self.undo = Gtk.Button(label='Previous palette')
        self.undo.connect('clicked', lambda _: self.apply('rollback'))
        header.pack_start(self.undo)
        self.button = Gtk.Button(label='Apply palette', css_classes=['suggested-action'])
        self.button.connect('clicked', lambda _: self.apply('apply'))
        header.pack_end(self.button)
        layout.append(header)
        explanation = Gtk.Label(label='GNOME palette · Native GNOME layout\nNiri remembers its own selection in Noctalia.',
                                margin_top=12, margin_bottom=12, wrap=True)
        layout.append(explanation)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=['boxed-list'],
                                margin_start=18, margin_end=18, margin_bottom=18)
        current = engine.selection()['palette']
        for name, path in engine.presets().items():
            row = Gtk.ListBoxRow()
            row.palette = name
            box = Gtk.Box(spacing=16, margin_start=16, margin_end=16, margin_top=13, margin_bottom=13)
            box.append(Gtk.Label(label=name.removeprefix('oma '), xalign=0, hexpand=True))
            palette = json.loads(path.read_text())['dark'] if path else {}
            if path is None:
                mode = 'Dark' if name == 'Vanilla Gnome Dark' else 'Light'
                box.append(Gtk.Label(label=f'Stock GNOME · {mode} · Adwaita icons\nKeeps your cursor',
                                     xalign=1, css_classes=['dim-label']))
            for key in (('mSurface', 'mSurfaceVariant', 'mOnSurface', 'mPrimary', 'mSecondary', 'mTertiary') if path else ()):
                area = Gtk.DrawingArea(content_width=22, content_height=22, tooltip_text=key + ': ' + palette[key])
                color = tuple(channel / 255 for channel in engine.rgb(palette[key]))
                def draw(_area, context, width, height, color=color):
                    context.set_source_rgb(*color)
                    context.arc(width / 2, height / 2, min(width, height) / 2 - 1, 0, 6.283185)
                    context.fill()
                area.set_draw_func(draw)
                box.append(area)
            row.set_child(box)
            self.list.append(row)
            if name == current:
                self.list.select_row(row)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER, child=self.list)
        layout.append(scroll)
        self.setup = Gtk.Button(label='Set up / Refresh integrations', margin_start=18, margin_end=18)
        self.setup.connect('clicked', lambda _: self.integrations('setup'))
        layout.append(self.setup)
        self.message = Gtk.Label(label='Selected: ' + current + ' · Some apps need reopening after a change.',
                                 wrap=True, margin_start=18, margin_end=18, margin_top=8, margin_bottom=18)
        layout.append(self.message)
        self.window.set_content(layout)
        self.window.present()

    def apply(self, action):
        row = self.list.get_selected_row()
        if row is None:
            return
        self.button.set_sensitive(False)
        self.undo.set_sensitive(False)
        self.list.set_sensitive(False)
        self.setup.set_sensitive(False)
        self.message.set_label('Applying palette…')
        command = ['/usr/bin/python3', str(Path(__file__).with_name('engine.py')), action]
        if action == 'apply':
            command.append(row.palette)
        def worker():
            result = subprocess.run(command, capture_output=True, text=True)
            GLib.idle_add(self.finished, result)
        threading.Thread(target=worker, daemon=True).start()

    def finished(self, result):
        self.button.set_sensitive(True)
        self.undo.set_sensitive(True)
        self.list.set_sensitive(True)
        self.setup.set_sensitive(True)
        if result.returncode:
            self.message.set_label('Could not apply palette: ' + result.stderr.strip()[-500:])
            return
        state = engine.selection()
        for index in range(len(engine.presets())):
            row = self.list.get_row_at_index(index)
            if row.palette == state['palette']:
                self.list.select_row(row)
        failed = [name for name, hook in state.get('hooks', {}).items() if not hook.get('ok') or hook.get('pending')]
        text = 'Applied ' + state['palette'] + '. Reopen apps that keep their old colors.'
        if state['palette'] not in ('Vanilla Gnome', 'Vanilla Gnome Dark') and not state.get('shell_extension', {}).get('active'):
            text += ' Shell theme needs User Themes enabled (or a fresh GNOME login).'
        if failed:
            text += ' Refresh pending: ' + ', '.join(failed) + '.'
        self.message.set_label(text)

    def integrations(self, action):
        if not getattr(self, 'integration_window', None):
            window = Adw.Window(transient_for=self.window, title='Application integrations',
                                default_width=760, default_height=620, modal=True)
            self.integration_window = window
            window.connect('close-request', self.integration_closed)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.append(Adw.HeaderBar())
            self.integration_message = Gtk.Label(wrap=True, xalign=0, margin_start=18, margin_end=18)
            box.append(self.integration_message)
            self.integration_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                                            margin_start=18, margin_end=18, margin_bottom=18)
            box.append(Gtk.ScrolledWindow(vexpand=True, child=self.integration_rows,
                                          hscrollbar_policy=Gtk.PolicyType.NEVER))
            controls = Gtk.Box(spacing=12, margin_start=18, margin_end=18, margin_bottom=18)
            self.integration_controls = []
            for label, command in (('Refresh status', 'status'), ('Set up / Refresh', 'setup'),
                                   ('Set up GDM (Administrator…)', 'admin-setup')):
                button = Gtk.Button(label=label)
                button.connect('clicked', lambda _, command=command: self.integrations(command))
                controls.append(button)
                self.integration_controls.append(button)
            box.append(controls)
            window.set_content(box)
        self.integration_window.present()
        self.integration_busy = True
        self.integration_message.set_label('Checking applications…' if action == 'status' else 'Setting up integrations… Close applications before profile changes. Missing optional apps are skipped.')
        for button in self.integration_controls + [self.setup, self.button, self.undo]:
            button.set_sensitive(False)
        command = ['/usr/bin/python3', str(Path(__file__).with_name('engine.py')), 'integrations', action]
        command += ['gdm'] if action == 'admin-setup' else ['--json']
        def worker():
            try:
                process = subprocess.run(command, capture_output=True, text=True)
            except OSError as error:
                process = subprocess.CompletedProcess(command, 1, '', str(error))
            GLib.idle_add(self.integrations_finished, process, action)
        threading.Thread(target=worker, daemon=True).start()

    def integration_closed(self, window):
        if getattr(self, 'integration_busy', False):
            return True
        self.integration_window = None
        return False

    def integrations_finished(self, process, action):
        self.integration_busy = False
        for button in self.integration_controls + [self.setup, self.button, self.undo]:
            button.set_sensitive(True)
        while self.integration_rows.get_first_child():
            self.integration_rows.remove(self.integration_rows.get_first_child())
        if action == 'admin-setup':
            self.integration_message.set_label((process.stdout if process.returncode == 0 else process.stderr)[-4000:])
            return
        try:
            report = json.loads(process.stdout)
        except (ValueError, TypeError):
            self.integration_message.set_label('Could not check integrations: ' + (process.stderr or process.stdout)[-2000:])
            return
        self.integration_message.set_label('Current preset: ' + report['palette'] +
            (' · Some integrations failed; see details below.' if report['failed'] else ' · Review each application’s status below.'))
        for row in report['results']:
            text = row['app'] + ' — ' + row['state'] + '\n' + row['target'] + '\n' + row['detail']
            if row.get('operation'):
                text += '\nRestore: project-largo integrations restore ' + row['operation']
            self.integration_rows.append(Gtk.Label(label=text, wrap=True, xalign=0, selectable=True))


if __name__ == '__main__':
    raise SystemExit(PalettePicker().run())
