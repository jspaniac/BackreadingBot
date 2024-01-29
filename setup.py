from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='backreading_bot',
    version='1.0',
    packages=find_packages(),
    install_requires=requirements,
    author='Joe Spaniac',
    author_email='jspaniac@yahoo.com',
    description='This script library allows CSE 12x/14x TAs perform various ' +
                'grading assistance checks',
    url='https://github.com/jspaniac/BackreadingBot',
    classifiers=[
        'Programming Language :: Python :: 3.9',
    ],
)
