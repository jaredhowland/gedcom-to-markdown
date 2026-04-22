# Example Canvas Plugin

This example package demonstrates how to publish a Canvas plugin for
`gedcom-to-markdown` using the `gedcom_to_markdown.canvas_plugins` entry
point group. Install locally using:

```bash
pip install -e examples/example_canvas_plugin
```

After installation, the plugin will be discoverable by the converter and
can be selected with `--canvas-plugin example` on the CLI.
