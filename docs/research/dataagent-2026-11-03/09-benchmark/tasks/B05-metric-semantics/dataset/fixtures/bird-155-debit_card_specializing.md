# BIRD mini / debit_card_specializing

## 问题

I want to gauge how spread out our high-value fuelling activity in the Czech Republic was over the recorded window. How many whole minutes elapsed from the first to the last fuel transaction at gas stations in the Czech Republic with a price over 1000? Please round down to whole minutes.

## 提示

Czech Republic means the gas station is in the CZE country.

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

