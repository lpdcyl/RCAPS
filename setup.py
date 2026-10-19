from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).resolve().parent
setup(
    name="rcaps-v3",
    version="3.0.0",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24,<3",
        "networkx>=3.2,<4",
        "matplotlib>=3.8,<4",
        "scipy>=1.11,<2",
        "gurobipy==13.0.3",
    ],
    author="RCAPS contributors",
    description="RCAPS V3 heterogeneous LLM serving research code built on Helix",
    long_description=(ROOT / "readme.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/lpdcyl/RCAPS",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
