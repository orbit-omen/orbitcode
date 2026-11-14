class Orbitcode < Formula
  desc "AI Coding Agent with model failover, MCP, plugins, and session persistence"
  homepage "https://github.com/OrbitOmen/orbitcode"
  url "https://github.com/OrbitOmen/orbitcode/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256_AFTER_RELEASE"
  license "MIT"
  head "https://github.com/OrbitOmen/orbitcode.git", branch: "main"

  depends_on "python@3.11"

  def install
    # Create virtual environment
    venv = virtualenv_create(libexec, "python3.11")

    # Install from GitHub (latest main branch)
    venv.pip_install "git+https://github.com/OrbitOmen/orbitcode.git@main#egg=orbitcode[dev,browser,web]"

    # Install playwright chromium
    system libexec/"bin/playwright", "install", "chromium"

    # Create wrapper scripts
    (bin/"orbitcode").write_env_script libexec/"bin/orbitcode", PYTHONPATH: libexec/"lib/python3.11/site-packages"
    (bin/"ocode").write_env_script libexec/"bin/ocode", PYTHONPATH: libexec/"lib/python3.11/site-packages"
  end

  def caveats
    <<~EOS
      OrbitCode has been installed!

      Quick start:
        orbitcode           # Start interactive mode
        orbitcode --setup   # Run setup wizard
        orbitcode --help    # Show all commands
        ocode               # Short alias

      Configuration:
        Set your OpenRouter API key:
          export OPENROUTER_API_KEY="your-key-here"

        Or run `orbitcode --setup` to configure interactively.

      Graphify Knowledge Graph:
        View at: /workspaces/codespaces-blank/graphify-out/graph.html
    EOS
  end

  test do
    system bin/"orbitcode", "--version"
    system bin/"ocode", "--version"
  end
end