from setuptools import setup, find_packages

setup(
    name="constructo",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'google-generativeai',
        'rich',
        'pyyaml'
    ]
)