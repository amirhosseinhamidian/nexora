from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PrivateRuntimeContainerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server_dockerfile = (ROOT / "apps/server/Dockerfile").read_text(encoding="utf-8")
        self.web_dockerfile = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")
        self.compose = (ROOT / "infra/compose/private-single-host.yml").read_text(encoding="utf-8")

    def test_server_image_runs_installed_entrypoint_without_runtime_sync(self) -> None:
        self.assertIn("PATH=/app/.venv/bin:$PATH", self.server_dockerfile)
        self.assertIn('CMD ["nexora-api"]', self.server_dockerfile)
        self.assertNotIn('CMD ["uv", "run"', self.server_dockerfile)

        worker = self.compose.split("\n  worker:\n", maxsplit=1)[1].split("\n  postgresql:\n", maxsplit=1)[0]
        self.assertIn('"nexora-worker"', worker)
        self.assertNotIn('"uv"', worker)

    def test_server_image_contains_migration_assets(self) -> None:
        self.assertIn("COPY --chown=65532:65532 alembic.ini ./", self.server_dockerfile)
        self.assertIn("COPY --chown=65532:65532 alembic ./alembic", self.server_dockerfile)

    def test_non_root_runtime_owns_application_and_volume_roots(self) -> None:
        self.assertIn("COPY --chown=65532:65532 pyproject.toml uv.lock ./", self.server_dockerfile)
        self.assertIn("COPY --chown=65532:65532 apps/server ./apps/server", self.server_dockerfile)
        self.assertIn("mkdir -p /var/lib/nexora/artifacts /var/log/nexora", self.server_dockerfile)
        self.assertIn("/app /var/lib/nexora/artifacts /var/log/nexora", self.server_dockerfile)
        self.assertIn("USER 65532:65532", self.server_dockerfile)

    def test_web_image_starts_next_from_workspace_binary(self) -> None:
        self.assertIn(
            'CMD ["./apps/web/node_modules/.bin/next", "start", "apps/web"]',
            self.web_dockerfile,
        )
        self.assertNotIn('CMD ["./node_modules/.bin/next"', self.web_dockerfile)

    def test_ingress_uses_loopback_bridge_and_internal_service_network(self) -> None:
        ingress = self.compose.split("\n  ingress:\n", maxsplit=1)[1].split("\n  web:\n", maxsplit=1)[0]
        self.assertIn(
            '"${NEXORA_PRIVATE_BIND_ADDRESS:?private overlay address required}:443:443"',
            ingress,
        )
        self.assertIn("networks: [loopback, ingress]", ingress)
        self.assertIn("\n  loopback:\n    internal: false\n", self.compose)
        self.assertIn("\n  ingress:\n    internal: true\n", self.compose)


if __name__ == "__main__":
    unittest.main()
