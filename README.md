# fava-envelope

A beancount fava extension to add a envelope budgeting capability to fava and beancount. It is developed as an fava plugin and CLI.

## Installation via pip
```
python install fava-envelope
```

## TODO

* add example file for screenshots and testing
* Add testing
* add charts

## Running fava-envelope

## Load the Extension
Add this to your beancount journal, and start fava as normal
```
2000-01-01 custom "fava-extension" "fava_envelope" "{}"
```

You should now see 'Envelope' in your fava window

## Setting up budget

### Set the budget start date
start date in the format <4 digit year>-<2 digit month>
```
2020-01-01 custom "envelope" "start date" "2020-01"
```

## Set up Budget Accounts
You will need to specify the Assets and Liabilities you want included in your budget (For example ignoring Investment accounts). you can use regular expression in these statements
```
2020-01-01 custom "envelope" "budget account" "Assets:Checking"
2020-01-01 custom "envelope" "budget account" "Liabilities:Credit-Cards:*"
```

### Set up mappings
By default fava-envelope will use the Assets/Liabilities/Income/Expenses buckets that are not listed in the budget accounts. this directive allows you to map them to another bucket
```
2020-01-01 custom "envelope" "mapping" "Expenses:Food:*" "Expenses:Food"
```

### Allocate money to a bucket
```
2020-01-31 custom "envelope" "allocate" "Expenses:Food" 100.00
```

### Set up operating currency
The envelopes will read the operating currency from the core beancount option.
```
option "operating_currency" "EUR"
```
It will default to USD if this option is not set. Only a single currency is supported for the budget. 

