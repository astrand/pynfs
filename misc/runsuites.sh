#!/bin/sh

SUITES=`./listsuites.py`
cd ..
pwd

for suite in $SUITES; do
    RESULT=`./nfs4st.py ford $suite 2>&1 | tail -n -1`
    echo "$suite $RESULT"
done

