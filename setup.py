from setuptools import setup, find_packages

setup(
    name="easy_slack",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "slack-sdk",
        "questionary",
        "click",
        "rich",
        "pywin32;platform_system=='Windows'",  # For JAWS
        "nvda-controller-client;platform_system=='Windows'"  # For NVDA
    ]
)