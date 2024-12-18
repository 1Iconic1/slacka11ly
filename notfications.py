from easy_slack import EasySlack, NotificationPriority, NotifySound, MessageType
import asyncio

async def main():
    slack = EasySlack()
    print("Connecting to Slack...")
    if not await slack.login("nikhilv1@uci.edu"):
        print("Failed to connect!")
        return

    # Create profile and rule for manager messages (keeping your existing one)
    slack.notify_manager.create_profile(
        name="manager_message1",
        sound_type=NotifySound.URGENT,
        title_template="Message from Manager",
        message_template="{sender}: {content}",
        priority=NotificationPriority.HIGH
    )

    # Create profile and rule for intern messages
    slack.notify_manager.create_profile(
        name="intern_message",
        sound_type=NotifySound.MESSAGE,  
        title_template="",  
        message_template="", 
        priority=NotificationPriority.LOW  
    )

    # Manager rule
    slack.when("message") \
        .from_person("kapilg@uci.edu") \
        .with_priority(NotificationPriority.HIGH) \
        .play_sound("manager_message1") \
        .done()

    # Intern rule
    slack.when("message") \
        .from_person("dwaynem@uci.edu") \
        .with_priority(NotificationPriority.LOW) \
        .play_sound("intern_message") \
        .done()

    print("\nSetup complete!")
    print("Will notify when your manager or intern messages:")
    print("- Manager: Urgent sound + voice message")
    print("- Intern: Simple notification sound only")
    print("\nPress Ctrl+C to stop")
    await slack.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")