"""CLI for the WebP worker."""

from __future__ import annotations

import logging
import sys

import click

from webp_shared.files import find_free_tcp_port

from .config import WorkerConfig
from .server import WorkerServer


@click.command()
@click.option("-h", "--host", default="127.0.0.1", help="Worker host")
@click.option("-p", "--port", default=5057, type=int, help="Worker port")
@click.option("--backend-host", default="127.0.0.1", help="Backend host")
@click.option("--backend-port", default=5055, type=int, help="Backend TCP port")
@click.option("--backend-udp-port", default=5056, type=int, help="Backend UDP port")
@click.option("-v", "--verbose", is_flag=True, help="Debug logging")
def cli(host: str, port: int, backend_host: str, backend_port: int,
        backend_udp_port: int, verbose: bool) -> None:
    """Run a WebP conversion worker."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    actual_port = find_free_tcp_port(host, port)
    if actual_port != port:
        logging.info("Port %d busy, using %d", port, actual_port)

    config = WorkerConfig(
        host=host,
        port=actual_port,
        backend_host=backend_host,
        backend_tcp_port=backend_port,
        backend_udp_port=backend_udp_port,
    )

    server = WorkerServer(config)
    try:
        server.run()
    except KeyboardInterrupt:
        logging.info("Interrupted")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
