# krita-8bfhost-bridge

krita-8bfhost-bridge is a Krita Python plug-in that runs Photoshop-compatible filter plug-ins (`.8bf` files) on Krita paint layers. It works on Windows, macOS and Linux; on Linux, Windows filters run under Wine.

8bf plugins, originally used by Photoshop, now work with a lot of programs: GIMP, Affinity, and quite a few others. It's not the newest format, but it works, and many people have commercial plugins - some of which are no longer available - which are in 8bf format.

This plugin requires [8bf-host](https://github.com/distortionary-labs/8bf-host), which is a separate program you install yourself. The plug-in adds the menus, hands the layer and selection to 8bf-host, and puts the result back into your image. As a side benefit, a filter that crashes takes 8bf-host down with it, not Krita.

## What works, and what doesn't

The plug-in supports:

- 8-bit and 16-bit RGB and 8-bit grayscale paint layers, with alpha.
- Selections, including anti-aliased and feathered edges. The result is blended through the selection mask, as Photoshop's "auto mask" does.
- Filter dialogs and previews, which 8bf-host displays.
- **Repeat Last Filter**, which reruns a filter with its saved settings and no dialog, even after a Krita restart.
- 16-bit layers with filters that only handle 8-bit data. 8bf-host runs the filter on an 8-bit copy and keeps the original 16-bit values for any pixel the filter left unchanged. You can turn this off.

There are a few limitations worth knowing before you depend on it:

- **Undo.** Krita's Python API does not record `setPixelData` in the undo history. By default, then, the result goes into a new layer above the active one, which you can hide or delete. The optional in-place mode overwrites the layer, and Ctrl+Z cannot reverse it.
- **Color modes.** CMYK, Lab, floating-point and 16-bit grayscale layers must be converted first. (16-bit grayscale is missing because 8bf-host cannot yet write that layout back as PAM, the image format the plug-in exchanges with it.)
- **Filter windows.** The dialog belongs to the 8bf-host process, so it may open behind Krita's window.
- **Progress.** 8bf-host does not report progress, so the progress dialog only shows that a filter is running. Cancel asks the filter to stop; on Windows it ends the 8bf-host process instead.
- **Filter compatibility.** Everything in 8bf-host's [compatibility notes](https://github.com/distortionary-labs/8bf-host/blob/main/docs/compatibility.md) applies. Some commercial filters check for Photoshop specifically and refuse to run anywhere else.

## Installation

You need Krita 5.x and 8bf-host. The plug-in uses only the Python standard library and PyQt, both of which ship with Krita.

First, install 8bf-host from its [releases page](https://github.com/distortionary-labs/8bf-host/releases) or with `cargo install`, and check that it starts:

```console
$ 8bf-host --version
8bf-host 0.1.0
```

On Linux, Windows filters also need Wine and the Windows build of 8bf-host; see 8bf-host's [Wine guide](https://github.com/distortionary-labs/8bf-host/blob/main/docs/wine.md), and run `8bf-host doctor` to confirm the setup. It's also worth checking your filters' licenses, since some commercial filters only permit use inside particular programs.

Next, install the plug-in. From a release zip, choose **Tools > Scripts > Import Python Plugin from File...**, pick `krita-8bfhost-bridge-<version>.zip`, restart Krita, and confirm that **Photoshop Filters (8bf)** is enabled under **Settings > Configure Krita > Python Plugin Manager**.

From a checkout, `scripts/install.sh` (or `make install`) copies the plug-in into your Krita profile and enables it:

```console
$ scripts/install.sh
Installed to /home/you/.local/share/krita/pykrita
Enabled in /home/you/.config/kritarc (previous version saved as /home/you/.config/kritarc.bak)
Start Krita and find the filters under Tools > Scripts.
```

The script knows the Linux and macOS profile locations; set `PYKRITA` and `KRITARC` for others, such as Windows or a Flatpak Krita. Krita rewrites `kritarc` when it exits, so if Krita is running, the script only copies files and you'll need to enable the plug-in by hand after a restart. `make package` builds the release zip into `dist/`.

Finally, open **Tools > Scripts > 8bf Filter Settings...** and set the location of 8bf-host on the **8bf-host** tab. If you leave it empty, the plug-in searches `PATH`, `~/.cargo/bin` and `~/.local/bin`. Of course, Krita started from a desktop menu often has a shorter `PATH` than your terminal, so setting it explicitly is more reliable. **Check Setup** runs `8bf-host doctor` and shows the result.

## Using the plug-in

The plug-in adds three entries under **Tools > Scripts**:

- **Photoshop Filters (8bf)**, a submenu of filters grouped by their own categories. Filters 8bf-host cannot run on your system are greyed out; the tooltip says why.
- **Repeat *name***, which reruns the last filter with its last settings.
- **8bf Filter Settings...**, for the 8bf-host location, filter folders, the filter list, About boxes and where results go.

8bf-host searches `~/8bf-plugins`, the folders in its own configuration and, on Windows and macOS, the usual Adobe plug-in folders. You can add more folders on the **Folders** tab.

To run a filter, select a paint layer, optionally make a selection, and pick the filter. When it finishes, the result appears in a new layer named *Layer (Filter)*. **Repeat Last 8bf Filter** is a good candidate for a keyboard shortcut under **Settings > Configure Krita > Keyboard Shortcuts**.

Behind the scenes, the plug-in writes the layer (and the selection, as a grayscale mask) to a temporary folder as PAM files, then runs `8bf-host run <filter id> layer.pam filtered.pam --dialog --save-preset <preset>` along with the selection bounds, Krita's foreground and background colors, and the document resolution. Repeat runs pass `--preset` instead of `--dialog`. Presets live in Krita's application data folder under `krita_8bfhost_bridge/presets`.

## Troubleshooting

If the menu says "8bf-host not set up," the plug-in could not find or run 8bf-host; set its location in the settings. If a filter is greyed out, the tooltip and the **Runs** column on the **Filters** tab give 8bf-host's reason. If a filter fails, **Show Details** in the error dialog shows 8bf-host's log, and you can reproduce the run from a terminal (`8bf-host run --help` describes the options).

For more detail, start Krita with `KRITA_8BFHOST_BRIDGE_DEBUG=1` to print each 8bf-host command and its log.

## Development

`devenv.nix` provides Python 3.12 (the version Krita 5.2 embeds), pytest, a C compiler and ruff. Run the tests with `make test`.

Some tests are skipped unless `EIGHTBF_HOST` points at a dynamically linked 8bf-host, since they load a native test filter built from `tests/fixtures/testfilter.c`. Linux release builds are static and cannot load `.so` filters, so we build one from an 8bf-host checkout:

```console
$ EIGHTBF_HOST=../8bf-host/target/release/8bf-host make test
```

`make krita-smoke` uses the same variable and also needs `krita` and `xvfb-run`. It installs the plug-in into a temporary Krita profile and drives the real menus under Xvfb, leaving your own settings alone. Run it from a shell whose Python environment variables don't point at a different Python than Krita's; otherwise Krita loads mismatched extension modules.

## License

MIT. See `LICENSE`. Photoshop is a trademark of Adobe.
