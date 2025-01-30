from setuptools import setup, find_packages

setup(
    name="constructo",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'google-generativeai>=0.3.0',
        'rich>=10.0.0',
        'prompt_toolkit>=3.0.0',
        'pyperclip>=1.8.0',
        'pyyaml>=6.0.0',
        'pexpect>=4.8.0'
    ],
    python_requires='>=3.8',
    description="An AI-powered security testing assistant",
    author="Constructo Team",
    author_email="contact@constructo.ai",
    url="https://github.com/constructo/constructo",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Security',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)