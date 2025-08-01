from easy_slack import EasySlack, NotificationPriority, NotifySound, MessageType
import asyncio

async def main():
    slack = EasySlack()
    print("Connecting to Slack...")
    if not await slack.login("dwaynem@uci.edu"):
        print("Failed to connect!")
        return

    # Create profile for channel notifications
    slack.notify_manager.create_profile(
        name="channel_notification",
        sound_type=NotifySound.MESSAGE,  # Basic notification sound
        title_template="Channel Update",  # Simple title
        message_template="New message in slacka11lytest",  # No content, just notification
        priority=NotificationPriority.LOW  # Low priority
    )

    # Create rule for channel monitoring
    slack.when("message") \
        .in_channel("slacka11lytest") \
        .with_priority(NotificationPriority.HIGH) \
        .play_sound("channel_notification") \
        .done()

    print("\nSetup complete!")
    print("Will notify when messages appear in #slacka11lytest:")
    print("- Simple notification sound")
    print("- Low priority: only in ACTIVE status")
    print("- Messages will be buffered in FOCUSED/DND modes")
    print("\nPress Ctrl+C to stop")
    await slack.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")