I am using the formula '=IFERROR(C2/B2,0)-1' to calculate the week-on-week difference in an Excel spreadsheet. However, when the value for the previous week is 0% and the value for the following week is 11%, the formula returns -100 instead of the expected result, which is empty. How can I correct this formula to get the right output?

My current formula is:
IFERROR(C2/B2,0)-1