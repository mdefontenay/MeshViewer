"""The window's units: the file's (what its numbers are in: asked the first time, File ▸
File Unit…, the toolbar's ✎) and the one lengths are shown in (the toolbar's unit ▾);
every tool that shows a length or a position follows."""
from __future__ import annotations

from meshviewer.gui.dialogs.units import FileUnitDialog, default_unit


class Units:
    def _sync_units(self):
        """Select the shown unit (the file's own unless another was picked)."""
        unit = self.scene.measure.display_unit or self.scene.model.units
        for a in self.a_units:
            a.setChecked(a.data() == unit)
        self.a_units_menu.setText(unit or "Units")      # the toolbar's pull-down

    def _ask_file_unit(self):
        """First time this file is opened: which unit are its numbers in?"""
        m = self.scene.model
        unit = default_unit(m, self.ctl.prefs)
        self._set_file_unit(unit)                      # works meanwhile; the answer replaces it
        if self.ctl.prefs["ask_unit"]:                 # Settings ▸ Units
            self._open_unit_sheet(unit)

    def _edit_file_unit(self):
        """Toolbar ✎: change the file's unit (the same sheet as on the first open)."""
        if self.scene is not None:
            self._open_unit_sheet(self.scene.model.units
                                  or default_unit(self.scene.model, self.ctl.prefs))

    def _open_unit_sheet(self, unit):
        self._unit_dialog = FileUnitDialog(self, self.path.name, unit,
                                           self.scene.model.file_units)
        self._unit_dialog.chosen.connect(self._set_file_unit)
        self._unit_dialog.open()

    def _set_file_unit(self, unit):
        sc = self.scene
        if sc is None or not unit:
            return
        sc.model.units = unit
        sc.measure.set_display_unit(sc.measure.display_unit)    # None: follows the file
        self._sync_units()
        self.sidebar.info_panel.refresh()
        self.sidebar.edit_panel.refresh()
        self.sidebar.cfd_panel.model_changed()         # lengths in metres
        self.sidebar.inflation_panel.model_changed()
        self.sidebar.contours_panel.length_unit_changed()   # positions X / Y / Z
        self.sidebar.plots_panel.model_changed()       # positions in the new unit

    def _unit_chosen(self, a):
        if self.scene:
            self.scene.measure.set_display_unit(a.data())
            self._sync_units()
            self.sidebar.info_panel.refresh()           # Info in the new unit
            self.sidebar.selected_panel.refresh()       # Measure Selected too
            self.sidebar._show_info(self.scene.selected_parts)   # a picked length / area
            self.sidebar.cfd_panel.model_changed()      # mesh length in metres
            self.sidebar.inflation_panel.model_changed()   # auto length in metres
            self.sidebar.contours_panel.length_unit_changed()   # positions X / Y / Z
            self.sidebar.plots_panel.model_changed()       # plots in the new unit
