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


def test_get_canvas_plugin_returns_registered():
    cls = get_canvas_plugin("stub")
    assert cls is StubPlugin
    inst = cls([], "/tmp")
    path = inst.generate_canvas("@I1@")
    assert isinstance(path, str)
    assert inst.called
