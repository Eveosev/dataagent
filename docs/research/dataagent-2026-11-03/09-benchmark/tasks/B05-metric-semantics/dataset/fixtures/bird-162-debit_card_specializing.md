# BIRD mini / debit_card_specializing

## 问题

For my February 2013 activity report: how many SME customers actually purchased gas in February 2013? Please give me just a single whole number - the count of SME customers who consumed gas during the calendar month of February 2013 (Feb 1-28, 2013).

## 提示

By "gas" I mean gasoline (motor fuel) purchases, not natural gas.

## Schema

CREATE TABLE `customers` (
    `CustomerID` INTEGER, -- identification of the customer; example: [3, 5]
    `Segment` TEXT, -- client segment; example: ['SME', 'LAM']
    `Currency` TEXT, -- Currency; example: ['EUR']
    PRIMARY KEY (`CustomerID`)
);

CREATE TABLE `gasstations` (
    `GasStationID` INTEGER, -- Gas Station ID; example: [44, 45]
    `ChainID` INTEGER, -- Chain ID; example: [13, 6]
    `Country` TEXT, -- example: ['CZE']
    `Segment` TEXT, -- chain segment; example: ['Value for money', 'Premium']
    PRIMARY KEY (`GasStationID`)
);

CREATE TABLE `products` (
    `ProductID` INTEGER, -- Product ID; example: [1, 2]
    `Description` TEXT, -- Description; example: ['Rucní zadání', 'Nafta']
    PRIMARY KEY (`ProductID`)
);

CREATE TABLE `transactions_1k` (
    `TransactionID` INTEGER, -- Transaction ID; example: [1, 2]
    `Date` DATE, -- Date; example: ['2012-08-24']
    `Time` TEXT, -- Time; example: ['09:41:00', '10:03:00']
    `CustomerID` INTEGER, -- Customer ID; example: [31543, 46707]
    `CardID` INTEGER, -- Card ID; example: [486621, 550134]
    `GasStationID` INTEGER, -- Gas Station ID; example: [3704, 656]
    `ProductID` INTEGER, -- Product ID; example: [2, 23]
    `Amount` INTEGER, -- Amount; example: [28, 18]
    `Price` REAL, -- Price; example: [672.64, 430.72]
    PRIMARY KEY (`TransactionID`)
);

CREATE TABLE `yearmonth` (
    `CustomerID` INTEGER, -- Customer ID; example: [5, 6]
    `Date` TEXT, -- Date; example: ['201207', '201302']
    `Consumption` REAL, -- consumption; example: [528.3, 1598.28]
    PRIMARY KEY (`CustomerID`, `Date`),
    FOREIGN KEY (`CustomerID`) REFERENCES `customers` (`CustomerID`)
);

