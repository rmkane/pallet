if [ $# -ne 1 ]; then
	echo usage: $0 "{index}"
	exit 1
fi

TESTDIR="test/"
mkdir -p "${TESTDIR}"

python mine/generateOrder.py "${TESTDIR}"

echo "Copying file ${TESTDIR}$1.order.xml"
cp "${TESTDIR}order.xml" "${TESTDIR}$1.order.xml"

echo Mine
./mine/run.sh "${TESTDIR}order.xml" "${TESTDIR}packlist1.xml" examples/icra2011/scoreAsPlannedConfig1.xml
./palletandtruckviewer-3.0/palletViewer -o "${TESTDIR}order.xml" -p "${TESTDIR}packlist1.xml" -s examples/icra2011/scoreAsPlannedConfig1.xml

echo Jacobs
./jacobs/run.sh "${TESTDIR}order.xml" "${TESTDIR}packlist2.xml" examples/icra2011/scoreAsPlannedConfig1.xml
./palletandtruckviewer-3.0/palletViewer -o "${TESTDIR}order.xml" -p "${TESTDIR}packlist2.xml" -s examples/icra2011/scoreAsPlannedConfig1.xml
