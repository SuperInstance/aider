"""Package setup for Aider Budget Enforcer."""

from setuptools import setup, find_packages

setup(
    name="aider-budget-enforcer",
    version="0.1.0",
    description="Token spending budget enforcement for Aider",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(include=["budget_enforcer", "budget_enforcer.*"]),
    python_requires=">=3.8",
    install_requires=[
        "aider-chat>=0.50.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0", "pytest-cov>=4.0"],
    },
    scripts=[
        "scripts/aider-budget",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
