{ pkgs, lib, config, inputs, ... }:

{
  # gcc builds the test filter; xvfb-run is only needed for `make krita-smoke`.
  # 8bf-host itself is not packaged here: point EIGHTBF_HOST at a build of it.
  packages = with pkgs; [ git gcc ruff xvfb-run zip ];

  languages.python = {
    enable = true;
    # Match the Python embedded in Krita 5.2.
    package = pkgs.python312.withPackages (ps: [ ps.pytest ]);
  };
}
