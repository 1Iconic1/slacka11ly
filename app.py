from flask import Flask, render_template, request, jsonify
import asyncio
import threading
from easy_slack import EasySlack, NotificationPriority, NotifySound


app = Flask(__name__)


def run_slack_bot(email):
    async def main():
        slack = EasySlack()
        print("Connecting to Slack...")
        if not await slack.login(email):
            print("Failed to connect!")
            return

        slack.notify_manager.create_profile(
            name="manager_message1",
            sound_type=NotifySound.URGENT,
            title_template="Message from Manager",
            message_template="{sender}: {content}",
            priority=NotificationPriority.HIGH
        )

        slack.notify_manager.create_profile(
            name="intern_message",
            sound_type=NotifySound.MESSAGE,
            title_template="",
            message_template="",
            priority=NotificationPriority.LOW
        )

        slack.when("message") \
            .from_person("djmorganjr22@gmail.com") \
            .with_priority(NotificationPriority.HIGH) \
            .play_sound("manager_message1") \
            .done()

        slack.when("message") \
            .from_person("dwaynemorgan2024@u.northwstern.edu") \
            .with_priority(NotificationPriority.HIGH) \
            .play_sound("intern_message") \
            .done()

        print("\nSetup complete!")
        print("Will notify when your manager or intern messages:")
        print("- Manager: Urgent sound + voice message")
        print("- Intern: Simple notification sound only")
        print("\nPress Ctrl+C to stop")
        await slack.start()
    
    asyncio.run(main())

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/connect', methods=['POST'])
def connect():
    email = request.form['email']
    thread = threading.Thread(target=run_slack_bot, args=(email,))
    thread.start()
    return jsonify({'status': 'success', 'message': f'Connecting to Slack with {email}'})

if __name__ == "__main__":
    app.run(debug=True)
