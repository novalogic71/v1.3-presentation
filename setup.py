from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="professional-audio-sync-analyzer",
    version="2.0.0",
    author="AMC Murray",
    author_email="your-email@company.com",
    description="Professional-grade audio synchronization analysis and repair system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/professional-audio-sync-analyzer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Sound/Audio :: Analysis",
        "Topic :: Multimedia :: Video :: Conversion",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.4.0",
        ],
        "gpu": [
            "torch>=2.0.0",
            "torchaudio>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sync-analyzer=sync_analyzer.cli.sync_cli:main",
            "sync-analyzer-web=web_ui.server:main",
        ],
    },
    include_package_data=True,
    package_data={
        "web_ui": ["*.html", "*.css", "*.js", "static/*"],
    },
    keywords="audio video sync synchronization broadcast television post-production",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/professional-audio-sync-analyzer/issues",
        "Source": "https://github.com/yourusername/professional-audio-sync-analyzer",
        "Documentation": "https://github.com/yourusername/professional-audio-sync-analyzer/docs",
    },
)
