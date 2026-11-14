# Maintainer: OrbitOmen <orbitomen@example.com>
pkgname=orbitcode
pkgver=0.1.0
pkgrel=1
pkgdesc="AI Coding Agent with model failover, MCP, plugins, and session persistence"
arch=('any')
url="https://github.com/OrbitOmen/orbitcode"
license=('MIT')
depends=('python>=3.11' 'python-pip' 'python-venv' 'git')
optdepends=('playwright: for browser automation'
            'chromium: for browser automation')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP') # Replace with actual sha256 after release

build() {
    cd "$pkgname-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "$pkgname-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl

    # Install license
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

    # Install documentation
    install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}

# Post-install message
post_install() {
    echo "OrbitCode installed successfully!"
    echo "Run 'orbitcode --setup' to configure your API keys."
    echo "Graphify Knowledge Graph available at: /workspaces/codespaces-blank/graphify-out/graph.html"
}