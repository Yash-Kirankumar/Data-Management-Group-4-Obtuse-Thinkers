#!/bin/zsh
# Run a Tableau Prep flow from the command line and show the real error if it fails.
#   tools/run_flow.sh prep/online_retail_flow.tfl
CLI="/Applications/Tableau Prep Builder (Apple silicon) 2026.2.app/Contents/scripts/tableau-prep-cli"
LOGS="$HOME/Documents/My Tableau Prep Repository/Command Line Repository/Logs"
OUT=$(mktemp)
"$CLI" -t "$1" > "$OUT" 2>&1
STATUS=$(tail -1 "$OUT")
echo "$STATUS"
if ! grep -q "Finished running the flow successfully" "$OUT"; then
  grep -E "message:|expression:" "$OUT" | sed 's/^ *//' | sort | uniq -c | head -20
  F=$(ls -t "$LOGS"/preprestapi*.log | head -1)
  grep -o 'Caused by: [^\\]*\|"Could not[^"]*\|Reading Maestro document fails[^"]*' "$F" | sort -u | head -5 | cut -c1-400
  grep -h "Could not open\|was not found" "$LOGS/cli.log" | tail -2
fi
rm -f "$OUT"
