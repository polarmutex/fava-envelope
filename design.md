# Design Goals for the Envelope Extension

## Reference for Design Considerations

[Beancount Envelope Budgeting Discussion](https://groups.google.com/forum/m/#!msg/beancount/kQMPTY5Q4ko/49hbQdyKCgAJ)
[fava issue](https://github.com/beancount/fava/issues/909)

## Design

My initial goal is make the extension a reporting feature on the beancount
journal. I do not want to have to do automatic transactions or doubling the
postings to achieve envelope budgeting.

The envelope transfers will be handled by custom directives

The planned configurations options are the following
 - The start of the budget
 - the Assets to be used in the budget
 - the envelope names
 - the mappings of expenses/income to envelopes
