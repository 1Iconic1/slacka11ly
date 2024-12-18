from easy_slack import EasySlack, NotificationPriority, NotifySound, MessageType
import asyncio

async def main():
    slack = EasySlack()
    print("Connecting to Slack...")
    if not await slack.login("nikhilv1@uci.edu"):
        print("Failed to connect!")
        return

    # Verify user IDs
    m_info = slack.get_user_by_email("jharwani@uci.edu")
    if m_info:
        print(f"Found Manager's Slack ID: {m_info.get('id')}")
    else:
        print("Could not find Manager's Slack ID!")

    # Create profile and rule for manager messages
    slack.notify_manager.create_profile(
        name="manager_message2",
        sound_type=NotifySound.URGENT,
        title_template="Message from this is test 2",
        message_template="{sender}: {content}",
        priority=NotificationPriority.HIGH
    )

    # Manager rule with direct ID
    if m_info:
        slack.when("message") \
            .from_person(m_info['id']) \
            .with_priority(NotificationPriority.HIGH) \
            .play_sound("manager_message2") \
            .done()
        print(f"Created rule for Managers with ID: {m_info['id']}")

    print("\nSetup complete!")
    print("Will notify when your manager messages")
    print("- Manager: Urgent sound + voice message")
    print("\nPress Ctrl+C to stop")
    await slack.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")