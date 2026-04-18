import pytest

from canvas_plugin import register_canvas_plugin, list_plugins, get_canvas_plugin


class StubPlugin:
    def __init__(self, individuals, output_dir):
        self.individuals = individuals
        self.output_dir = output_dir
        self.called = False

    def generate_canvas(self, root_person_id, canvas_filename="Family Tree.canvas"):
        # Simulate writing a canvas and return path
        self.called = True
        return f"{self.output_dir}/{canvas_filename}"


def test_register_and_list_plugins():
    register_canvas_plugin("stub", StubPlugin)
    plugins = list_plugins()
    assert "stub" in plugins
    assert plugins["stub"] is StubPlugin


def test_list_plugins_always_includes_default():
    plugins = list_plugins()
    assert "default" in plugins


def test_get_canvas_plugin_returns_registered():
    register_canvas_plugin("stub", StubPlugin)
    cls = get_canvas_plugin("stub")
    assert cls is StubPlugin
    inst = cls([], "/tmp")
    path = inst.generate_canvas("@I1@")
    assert isinstance(path, str)
    assert inst.called


def test_get_canvas_plugin_raises_for_unknown():
    with pytest.raises(ValueError, match="Unknown canvas plugin: no_such_plugin"):
        get_canvas_plugin("no_such_plugin")
