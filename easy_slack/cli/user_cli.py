import click
import questionary
from rich.console import Console
from rich.table import Table
from pathlib import Path
import asyncio
import importlib.util
import sys
from ..core.easy_slack import EasySlack
from ..core.models import UserStatus, NotificationPriority, NotifySound, MessageType

console = Console()

@click.group()
def cli():
    """EasySlack User CLI"""
    pass

@cli.command()
@click.option('--email', prompt='Your email', help='Your workspace email')
def login(email: str):
    """Login to EasySlack"""
    try:
        slack = EasySlack()
        if asyncio.run(slack.login(email)):
            console.print("[green]Login successful[/green]")
        else:
            console.print("[red]Login failed[/red]")
    except Exception as e:
        console.print(f"[red]Error during login: {str(e)}[/red]")

@cli.command()
@click.argument('script_path', type=click.Path(exists=True))
def run_script(script_path: str):
    """Run a custom EasySlack script"""
    try:
        # Get absolute path
        script_path = str(Path(script_path).resolve())
        
        # Load the script as a module
        spec = importlib.util.spec_from_file_location("custom_script", script_path)
        if not spec or not spec.loader:
            console.print("[red]Invalid script file[/red]")
            return
            
        module = importlib.util.module_from_spec(spec)
        sys.modules["custom_script"] = module
        spec.loader.exec_module(module)
        
        # Run the script
        if hasattr(module, 'main'):
            console.print(f"[green]Running script: {Path(script_path).name}[/green]")
            if asyncio.iscoroutinefunction(module.main):
                asyncio.run(module.main())
            else:
                module.main()
        else:
            console.print("[red]Script must have a main function[/red]")
            
    except Exception as e:
        console.print(f"[red]Error running script: {str(e)}[/red]")

@cli.command()
def create_notification():
    """Create a custom notification profile"""
    try:
        slack = EasySlack()
        
        # Get notification details
        answers = questionary.form(
            name=questionary.text("Profile name:"),
            sound=questionary.select(
                "Notification sound:",
                choices=[s.value for s in NotifySound]
            ),
            title=questionary.text("Notification title:"),
            message=questionary.text("Message template:"),
            priority=questionary.select(
                "Priority:",
                choices=[p.value for p in NotificationPriority]
            )
        ).ask()
        
        if answers:
            success = slack.notify_manager.create_profile(
                name=answers['name'],
                sound_type=NotifySound(answers['sound']),
                title_template=answers['title'],
                message_template=answers['message'],
                priority=NotificationPriority(answers['priority'])
            )
            
            if success:
                console.print("[green]Notification profile created![/green]")
            else:
                console.print("[red]Failed to create notification profile[/red]")
                
    except Exception as e:
        console.print(f"[red]Error creating notification: {str(e)}[/red]")

@cli.command()
def create_rule():
    """Create a new notification rule"""
    try:
        slack = EasySlack()
        
        # Get rule type
        rule_type = questionary.select(
            "Select rule type:",
            choices=[
                "Message from person",
                "Message in channel",
                "Mention",
                "Keyword"
            ]
        ).ask()
        
        if not rule_type:
            return
            
        # Start building rule
        builder = slack.when(rule_type.lower().replace(" ", "_"))
        
        # Get conditions based on type
        if rule_type == "Message from person":
            who = questionary.text("Enter person's email:").ask()
            user = slack.db.get_user_by_email(who)
            if user:
                builder = builder.from_person(user['id'])
            else:
                console.print("[red]User not found[/red]")
                return
                
        elif rule_type == "Message in channel":
            channel = questionary.text("Enter channel name:").ask()
            builder = builder.in_channel(channel)
            
        elif rule_type == "Keyword":
            pattern = questionary.text("Enter keyword or pattern:").ask()
            builder = builder.containing(pattern)
        
        # Get priority
        priority = questionary.select(
            "Select priority:",
            choices=[p.value for p in NotificationPriority]
        ).ask()
        
        if priority:
            builder = builder.with_priority(NotificationPriority(priority))
        
        # Get actions
        while True:
            action = questionary.select(
                "Add action:",
                choices=["Play sound", "Speak message", "Done"]
            ).ask()
            
            if action == "Done":
                break
                
            if action == "Play sound":
                # Show available profiles
                profiles = list(slack.notify_manager.profiles.keys())
                profile = questionary.select(
                    "Select notification profile:",
                    choices=profiles
                ).ask()
                
                if profile:
                    message = questionary.text(
                        "Custom message (optional):"
                    ).ask()
                    builder = builder.play_sound(profile, message=message)
                    
            elif action == "Speak message":
                message = questionary.text("Enter message template:").ask()
                builder = builder.speak(message)
        
        # Finalize rule
        rule = builder.done()
        console.print("[green]Rule created successfully![/green]")
        
    except Exception as e:
        console.print(f"[red]Error creating rule: {str(e)}[/red]")

@cli.command()
def set_status():
    """Set user status"""
    try:
        slack = EasySlack()
        
        status = questionary.select(
            "Select status:",
            choices=[s.value for s in UserStatus]
        ).ask()
        
        if status:
            slack.set_status(UserStatus(status))
            console.print(f"[green]Status set to: {status}[/green]")
            
    except Exception as e:
        console.print(f"[red]Error setting status: {str(e)}[/red]")

@cli.command()
def manage_exceptions():
    """Manage notification exceptions"""
    try:
        slack = EasySlack()
        
        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Add exception",
                "Remove exception",
                "List exceptions"
            ]
        ).ask()
        
        if action == "Add exception":
            email = questionary.text("Enter email to add exception:").ask()
            slack.add_exception(email)
            console.print("[green]Exception added[/green]")
            
        elif action == "Remove exception":
            exceptions = slack.status_manager.buffer.exceptions
            if not exceptions:
                console.print("No exceptions configured")
                return
                
            user_id = questionary.select(
                "Select exception to remove:",
                choices=exceptions
            ).ask()
            
            if user_id:
                slack.status_manager.remove_exception(user_id)
                console.print("[green]Exception removed[/green]")
                
        elif action == "List exceptions":
            exceptions = slack.status_manager.buffer.exceptions
            if exceptions:
                table = Table()
                table.add_column("User ID")
                table.add_column("Name")
                
                for user_id in exceptions:
                    user = slack.db.get_user_by_slack_id(user_id)
                    if user:
                        table.add_row(user_id, user['name'])
                        
                console.print(table)
            else:
                console.print("No exceptions configured")
                
    except Exception as e:
        console.print(f"[red]Error managing exceptions: {str(e)}[/red]")

@cli.command()
def list_rules():
    """List all notification rules"""
    try:
        slack = EasySlack()
        rules = slack.rule_engine.rules
        
        if rules:
            table = Table()
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Priority")
            table.add_column("Actions")
            table.add_column("Status")
            
            for rule in rules.values():
                condition_type = next(iter(rule.conditions.keys()), "any")
                action_count = len(rule.actions)
                
                table.add_row(
                    rule.name,
                    condition_type,
                    rule.priority.value,
                    str(action_count),
                    "Enabled" if rule.enabled else "Disabled"
                )
                
            console.print(table)
        else:
            console.print("No rules configured")
            
    except Exception as e:
        console.print(f"[red]Error listing rules: {str(e)}[/red]")

@cli.command()
def start():
    """Start EasySlack"""
    try:
        slack = EasySlack()
        console.print("[green]Starting EasySlack...[/green]")
        asyncio.run(slack.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")

@cli.group()
def rules():
    """Manage notification rules"""
    pass

@rules.command()
def add():
    """Add a new notification rule"""
    try:
        slack = EasySlack()
        
        # Get rule type
        rule_type = questionary.select(
            "Select rule type:",
            choices=[
                "Message from person",
                "Message in channel",
                "Keyword in message"
            ]
        ).ask()
        
        if rule_type == "Message from person":
            email = questionary.text("Enter person's email:").ask()
            name = questionary.text("Give this rule a name:").ask()
            priority = questionary.select(
                "Select priority:",
                choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            ).ask()
            
            slack.when("message") \
                .from_person(email) \
                .with_priority(NotificationPriority[priority]) \
                .play_sound("default") \
                .done()
                
            print(f"Rule created: Notifications for messages from {email}")
            
        elif rule_type == "Message in channel":
            channel = questionary.text("Enter channel name:").ask()
            name = questionary.text("Give this rule a name:").ask()
            priority = questionary.select(
                "Select priority:",
                choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            ).ask()
            
            slack.when("message") \
                .in_channel(channel) \
                .with_priority(NotificationPriority[priority]) \
                .play_sound("default") \
                .done()
                
            print(f"Rule created: Notifications for messages in #{channel}")
            
        elif rule_type == "Keyword in message":
            keyword = questionary.text("Enter keyword or pattern:").ask()
            name = questionary.text("Give this rule a name:").ask()
            priority = questionary.select(
                "Select priority:",
                choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            ).ask()
            
            slack.when("message") \
                .containing(keyword) \
                .with_priority(NotificationPriority[priority]) \
                .play_sound("default") \
                .done()
                
            print(f"Rule created: Notifications for messages containing '{keyword}'")
            
    except Exception as e:
        print(f"Error creating rule: {e}")

@rules.command()
def list():
    """List all notification rules"""
    try:
        slack = EasySlack()
        # Directly get rules from database, no login needed
        rules = slack.db.get_rules()
        
        if not rules:
            console.print("[yellow]No rules configured[/yellow]")
            return
            
        # Create a table for better visualization
        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Conditions", style="green")
        table.add_column("Priority", style="yellow")
        table.add_column("Status", style="blue")
        
        for rule in rules:
            conditions = rule.get('conditions', {})
            table.add_row(
                rule.get('name', 'Unknown'),
                next(iter(conditions.keys()), "any"),
                ", ".join(f"{k}={v}" for k, v in conditions.items()),
                rule.get('priority', 'UNKNOWN'),
                "✓ Enabled" if rule.get('enabled', False) else "✗ Disabled"
            )
            
        console.print("\n[bold]Current Notification Rules:[/bold]")
        console.print(table)
            
    except Exception as e:
        console.print(f"[red]Error listing rules: {e}[/red]")

@rules.command()
def delete():
    """Delete a notification rule"""
    try:
        slack = EasySlack()
        rules = slack.rule_engine.rules
        
        if not rules:
            print("No rules to delete")
            return
            
        rule_choices = [f"{rule.name} ({rule.id})" for rule in rules.values()]
        selected = questionary.select(
            "Select rule to delete:",
            choices=rule_choices
        ).ask()
        
        if selected:
            rule_id = selected.split("(")[-1].strip(")")
            slack.rule_engine.remove_rule(rule_id)
            print(f"Rule deleted: {selected}")
            
    except Exception as e:
        print(f"Error deleting rule: {e}")

if __name__ == '__main__':
    cli()