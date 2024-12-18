import click
import questionary
from rich.console import Console
from rich.table import Table
from pathlib import Path
import asyncio
from ..core.easy_slack import EasySlack
from ..core.models import NotifySound, NotificationPriority
from ..utils.db import Database

console = Console()

@click.group()
def cli():
    """EasySlack Setup CLI"""
    pass

@cli.command()
@click.option('--slack-token', prompt='Enter your Slack Bot Token (xoxb-...)', 
              help='Slack Bot User OAuth Token')
@click.option('--app-token', prompt='Enter your Slack App Token (xapp-...)',
              help='Slack App-Level Token')
@click.option('--user-token', prompt='Enter your Slack User Token (xoxp-...)',
              help='Slack User OAuth Token')
def setup(slack_token: str, app_token: str, user_token: str):
    """Initial setup of workspace"""
    try:
        # Create config directory
        config_dir = Path.home() / '.easy_slack'
        config_dir.mkdir(exist_ok=True)
        
        # Initialize database
        db = Database(config_dir / 'workspace.db')
        
        # Save all tokens including user token
        db.save_tokens(slack_token, app_token, user_token)
        
        # Initialize EasySlack to test connection
        slack = EasySlack(config_dir)
        asyncio.run(test_connection(slack))
        
        console.print("[green]Setup completed successfully![/green]")
        
    except Exception as e:
        console.print(f"[red]Error during setup: {str(e)}[/red]")

async def test_connection(slack: EasySlack) -> bool:
    """Test Slack connection"""
    try:
        # Try to connect
        await slack.login("test@test.com")  # Temporary login for testing
        console.print("[green]Successfully connected to Slack![/green]")
        return True
    except Exception as e:
        console.print(f"[red]Connection test failed: {str(e)}[/red]")
        return False

@cli.command()
@click.option('--email', prompt='Admin email',
              help='Workspace admin email')
def add_admin(email: str):
    """Add workspace admin"""
    try:
        config_dir = Path.home() / '.easy_slack'
        db = Database(config_dir / 'workspace.db')
        
        admin_id = db.add_user(
            email=email,
            name="Admin",
            role="admin"
        )
        
        console.print(f"[green]Added admin: {email}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error adding admin: {str(e)}[/red]")

@cli.command()
def configure_notifications():
    """Configure default notification settings"""
    try:
        slack = EasySlack()
        
        # Get default settings
        settings = questionary.form(
            default_sound=questionary.select(
                "Default notification sound:",
                choices=[s.value for s in NotifySound]
            ),
            urgent_sound=questionary.select(
                "Urgent notification sound:",
                choices=[s.value for s in NotifySound]
            ),
            mention_sound=questionary.select(
                "Mention notification sound:",
                choices=[s.value for s in NotifySound]
            ),
            dm_sound=questionary.select(
                "Direct message sound:",
                choices=[s.value for s in NotifySound]
            )
        ).ask()
        
        if settings:
            # Configure notification profiles
            slack.notify_manager.create_profile(
                "default",
                NotifySound(settings['default_sound']),
                "Slack Message",
                "New message received",
                NotificationPriority.MEDIUM
            )
            
            slack.notify_manager.create_profile(
                "urgent",
                NotifySound(settings['urgent_sound']),
                "Urgent Message",
                "URGENT: {content}",
                NotificationPriority.HIGH
            )
            
            slack.notify_manager.create_profile(
                "mention",
                NotifySound(settings['mention_sound']),
                "Mention",
                "{sender} mentioned you",
                NotificationPriority.HIGH
            )
            
            slack.notify_manager.create_profile(
                "dm",
                NotifySound(settings['dm_sound']),
                "Direct Message",
                "DM from {sender}",
                NotificationPriority.HIGH
            )
            
            console.print("[green]Notification settings saved![/green]")
            
    except Exception as e:
        console.print(f"[red]Error configuring notifications: {str(e)}[/red]")

@cli.command()
def show_config():
    """Show current configuration"""
    try:
        config_dir = Path.home() / '.easy_slack'
        db = Database(config_dir / 'workspace.db')
        
        # Show workspace info
        console.print("\n[bold]Workspace Configuration[/bold]")
        tokens = db.get_tokens()
        if tokens:
            console.print("✓ Slack tokens configured")
        else:
            console.print("✗ Slack tokens not configured")
            
        # Show admins
        console.print("\n[bold]Administrators[/bold]")
        admins = db.get_users_by_role("admin")
        if admins:
            table = Table()
            table.add_column("Email")
            table.add_column("Name")
            
            for admin in admins:
                table.add_row(admin['email'], admin['name'])
                
            console.print(table)
        else:
            console.print("No administrators configured")
            
        # Show notification settings
        console.print("\n[bold]Notification Profiles[/bold]")
        slack = EasySlack(config_dir)
        profiles = slack.notify_manager.profiles
        
        if profiles:
            table = Table()
            table.add_column("Name")
            table.add_column("Sound")
            table.add_column("Priority")
            
            for name, profile in profiles.items():
                table.add_row(
                    name,
                    profile.sound_type.value,
                    profile.priority.value
                )
                
            console.print(table)
        else:
            console.print("No notification profiles configured")
            
    except Exception as e:
        console.print(f"[red]Error showing configuration: {str(e)}[/red]")

if __name__ == '__main__':
    cli()