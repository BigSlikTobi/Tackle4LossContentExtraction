from setuptools import setup, find_packages

setup(
    name="Tackle4LossContentExtraction",
    version="0.1.0",
    packages=find_packages(),
    # Add other metadata like author, description, etc. if you want
    install_requires=[
        "crawl4ai==0.4.248",
        "litellm==1.67.2",
        "nest_asyncio",
        "requests",
        "supabase>=2.13.0",
        "playwright",
        "python-dotenv>=1.0.0",
        "pytest",
        "openai>=1.0.0",
        "PyYAML",
        "httpx>=0.25.0",
        "numpy>=1.26.0",
        "scikit-learn>=1.4.0",
        "python-dateutil",
    ],
    entry_points={
        "console_scripts": [
            # If you have any command-line scripts, define them here
            # e.g., "my-script=Tackle4LossContentExtraction.cli:main",
        ],
    },
)
