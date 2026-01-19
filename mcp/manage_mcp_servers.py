#!/usr/bin/env python3
"""
MCP Servers Docker Compose Management Tool

This script provides a CLI interface to manage Docker Compose services
for all MCP servers in the mcp/ directory.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
import json


class MCPServerManager:
    """Manages Docker Compose services for MCP servers."""

    def __init__(self, mcp_dir: Path):
        self.mcp_dir = mcp_dir
        self.servers = self._discover_servers()

    def _discover_servers(self) -> List[str]:
        """Discover all MCP servers with docker-compose.yml files."""
        servers = []
        for item in self.mcp_dir.iterdir():
            if item.is_dir():
                compose_file = item / "docker-compose.yml"
                if compose_file.exists():
                    servers.append(item.name)
        return sorted(servers)

    def _run_compose_command(
        self,
        server: str,
        command: str,
        extra_args: Optional[List[str]] = None,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a docker-compose command for a specific server."""
        server_path = self.mcp_dir / server
        compose_file = server_path / "docker-compose.yml"

        if not compose_file.exists():
            raise FileNotFoundError(
                f"docker-compose.yml not found for server: {server}"
            )

        cmd = ["docker", "compose", "-f", str(compose_file), *command.split()]
        if extra_args:
            cmd.extend(extra_args)

        result = subprocess.run(
            cmd,
            cwd=server_path,
            capture_output=capture_output,
            text=True,
        )
        return result

    def _ensure_network(self):
        """Ensure the investment-net network exists."""
        result = subprocess.run(
            ["docker", "network", "inspect", "investment-net"],
            capture_output=True,
        )
        if result.returncode != 0:
            print("Creating investment-net network...")
            subprocess.run(
                ["docker", "network", "create", "investment-net"],
                check=True,
            )
            print("✓ Network created")
        else:
            print("✓ Network already exists")

    def start(self, server: Optional[str] = None, build: bool = False, unified: bool = False):
        """Start one or all MCP servers.
        
        Args:
            server: Specific server to start (optional)
            build: Whether to rebuild images
            unified: Use unified docker-compose.yml if available
        """
        # Check for unified compose file
        unified_compose = self.mcp_dir / "docker-compose.yml"
        if unified and unified_compose.exists():
            print(f"\n{'='*60}")
            print("Starting all MCP servers (unified mode)...")
            print(f"{'='*60}")
            self._ensure_network()
            
            cmd = ["docker", "compose", "-f", str(unified_compose), "up", "-d"]
            if build:
                cmd.append("--build")
            
            result = subprocess.run(cmd, cwd=self.mcp_dir, capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ All servers started successfully")
            else:
                print("✗ Failed to start servers")
                if result.stderr:
                    print(result.stderr)
                sys.exit(1)
            return
        
        # Individual server mode
        if server:
            if server not in self.servers:
                print(f"Error: Server '{server}' not found")
                print(f"Available servers: {', '.join(self.servers)}")
                sys.exit(1)
            servers_to_start = [server]
        else:
            servers_to_start = self.servers
            self._ensure_network()

        for srv in servers_to_start:
            print(f"\n{'='*60}")
            print(f"Starting {srv}...")
            print(f"{'='*60}")
            extra_args = ["--build"] if build else []
            result = self._run_compose_command(srv, "up -d", extra_args)
            if result.returncode == 0:
                print(f"✓ {srv} started successfully (running in background)")
            else:
                print(f"✗ Failed to start {srv}")
                if result.stderr:
                    print(result.stderr)
                sys.exit(1)

    def stop(self, server: Optional[str] = None, unified: bool = False):
        """Stop one or all MCP servers.
        
        Args:
            server: Specific server to stop (optional)
            unified: Use unified docker-compose.yml if available
        """
        # Check for unified compose file
        unified_compose = self.mcp_dir / "docker-compose.yml"
        if unified and unified_compose.exists():
            print(f"\n{'='*60}")
            print("Stopping all MCP servers (unified mode)...")
            print(f"{'='*60}")
            
            cmd = ["docker", "compose", "-f", str(unified_compose), "down"]
            result = subprocess.run(cmd, cwd=self.mcp_dir, capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ All servers stopped successfully")
            else:
                print("✗ Failed to stop servers")
                if result.stderr:
                    print(result.stderr)
            return
        
        # Individual server mode
        if server:
            if server not in self.servers:
                print(f"Error: Server '{server}' not found")
                print(f"Available servers: {', '.join(self.servers)}")
                sys.exit(1)
            servers_to_stop = [server]
        else:
            servers_to_stop = self.servers

        for srv in servers_to_stop:
            print(f"\n{'='*60}")
            print(f"Stopping {srv}...")
            print(f"{'='*60}")
            result = self._run_compose_command(srv, "down")
            if result.returncode == 0:
                print(f"✓ {srv} stopped successfully")
            else:
                print(f"✗ Failed to stop {srv}")
                if result.stderr:
                    print(result.stderr)

    def restart(self, server: Optional[str] = None, build: bool = False):
        """Restart one or all MCP servers."""
        self.stop(server)
        self.start(server, build=build)

    def status(self, server: Optional[str] = None):
        """Show status of one or all MCP servers."""
        if server:
            if server not in self.servers:
                print(f"Error: Server '{server}' not found")
                print(f"Available servers: {', '.join(self.servers)}")
                sys.exit(1)
            servers_to_check = [server]
        else:
            servers_to_check = self.servers

        print(f"\n{'='*60}")
        print("MCP Servers Status")
        print(f"{'='*60}\n")

        # Server endpoints mapping
        endpoints = {
            "damodaran_valuation": "http://localhost:8100/sse",
            "fundamentus_b3": "http://localhost:8101/sse",
        }

        for srv in servers_to_check:
            print(f"📦 {srv}")
            result = self._run_compose_command(
                srv, "ps", capture_output=True
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    # Skip the header line and show container status
                    lines = output.split("\n")[1:]
                    for line in lines:
                        if line.strip():
                            print(f"   {line}")
                    # Show connection endpoint
                    if srv in endpoints:
                        print(f"   🌐 MCP Endpoint: {endpoints[srv]}")
                else:
                    print("   No containers running")
            else:
                print(f"   Error checking status: {result.stderr}")
            print()

    def logs(self, server: str, follow: bool = False, tail: int = 100):
        """Show logs for a specific MCP server."""
        if server not in self.servers:
            print(f"Error: Server '{server}' not found")
            print(f"Available servers: {', '.join(self.servers)}")
            sys.exit(1)

        extra_args = ["--follow"] if follow else []
        extra_args.extend(["--tail", str(tail)])

        result = self._run_compose_command(
            server, "logs", extra_args, capture_output=False
        )
        if result.returncode != 0:
            sys.exit(1)

    def list_servers(self):
        """List all available MCP servers."""
        print(f"\n{'='*60}")
        print("Available MCP Servers")
        print(f"{'='*60}\n")
        if not self.servers:
            print("No MCP servers found with docker-compose.yml files")
        else:
            for i, server in enumerate(self.servers, 1):
                print(f"{i}. {server}")
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage Docker Compose services for MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s start                    # Start all servers
  %(prog)s start damodaran_valuation # Start specific server
  %(prog)s stop                     # Stop all servers
  %(prog)s restart --build          # Restart all with rebuild
  %(prog)s status                   # Show status of all servers
  %(prog)s logs damodaran_valuation # Show logs for a server
  %(prog)s logs damodaran_valuation --follow  # Follow logs
        """,
    )

    parser.add_argument(
        "--mcp-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Path to MCP directory (default: script directory)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start MCP server(s)")
    start_parser.add_argument(
        "server", nargs="?", help="Specific server to start (optional)"
    )
    start_parser.add_argument(
        "--build",
        action="store_true",
        help="Build images before starting",
    )
    start_parser.add_argument(
        "--unified",
        action="store_true",
        help="Use unified docker-compose.yml (starts all servers together)",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop MCP server(s)")
    stop_parser.add_argument(
        "server", nargs="?", help="Specific server to stop (optional)"
    )
    stop_parser.add_argument(
        "--unified",
        action="store_true",
        help="Use unified docker-compose.yml (stops all servers together)",
    )

    # Restart command
    restart_parser = subparsers.add_parser(
        "restart", help="Restart MCP server(s)"
    )
    restart_parser.add_argument(
        "server", nargs="?", help="Specific server to restart (optional)"
    )
    restart_parser.add_argument(
        "--build",
        action="store_true",
        help="Build images before restarting",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status", help="Show status of MCP server(s)"
    )
    status_parser.add_argument(
        "server", nargs="?", help="Specific server to check (optional)"
    )

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show logs for a server")
    logs_parser.add_argument("server", help="Server to show logs for")
    logs_parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow log output"
    )
    logs_parser.add_argument(
        "--tail",
        type=int,
        default=100,
        help="Number of lines to show from the end (default: 100)",
    )

    # List command
    subparsers.add_parser("list", help="List all available MCP servers")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = MCPServerManager(args.mcp_dir)

    try:
        if args.command == "start":
            manager.start(args.server, build=args.build, unified=args.unified)
        elif args.command == "stop":
            manager.stop(args.server, unified=args.unified)
        elif args.command == "restart":
            manager.restart(args.server, build=args.build)
        elif args.command == "status":
            manager.status(args.server)
        elif args.command == "logs":
            manager.logs(args.server, follow=args.follow, tail=args.tail)
        elif args.command == "list":
            manager.list_servers()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
