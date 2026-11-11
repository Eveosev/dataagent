CREATE TABLE party (
    party_no TEXT PRIMARY KEY,
    nm TEXT NOT NULL
);

CREATE TABLE doc_hdr (
    book TEXT NOT NULL,
    doc_no INTEGER NOT NULL,
    party_no TEXT NOT NULL,
    PRIMARY KEY (book, doc_no)
);

CREATE TABLE doc_line (
    book TEXT NOT NULL,
    doc_no INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    cents INTEGER NOT NULL,
    PRIMARY KEY (book, doc_no, seq),
    FOREIGN KEY (book, doc_no) REFERENCES doc_hdr
);

INSERT INTO party VALUES ('P-1', 'Acme'), ('P-2', 'Blue');
INSERT INTO doc_hdr VALUES ('SALE', 1001, 'P-1'), ('SALE', 1002, 'P-2');
INSERT INTO doc_line VALUES ('SALE', 1001, 1, 500), ('SALE', 1001, 2, 700), ('SALE', 1002, 1, 800);
