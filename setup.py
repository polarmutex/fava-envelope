from os import path
from setuptools import find_packages, setup

with open(path.join(path.dirname(__file__), 'README.md')) as readme:
    LONG_DESCRIPTION = readme.read()

setup(
    name='fava-envelope',
    version='1.0',
    description='Fava Envelope budgeting for beancout',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/bryall/fava-envelope',
    author='Brian RYall',
    author_email='bryall@gmail.com',
    license='MIT',
    keywords='fava beancount accounting budgeting',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'beancount>=2.2.3',
        'fava>=1.13',
        'pandas>=1.0.0'
    ],
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Financial and Insurance Industry',
        'License :: OSI Approved :: MIT',
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Office/Business :: Financial :: Accounting'
    ],
)
