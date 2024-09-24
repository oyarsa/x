package main

import (
	"fmt"
	"os"
	"strings"
	"time"
)

const (
	underline = "\033[4m"
	reset     = "\033[0m"
)

func generateCalendar(today, start, end time.Time) string {
	var calendar []string
	for current := start; !current.After(end); current = current.AddDate(0, 0, 7) {
		week := make([]string, 7)
		// Week starts on Monday
		weekStart := current.AddDate(0, 0, -int(current.Weekday())+1)

		for i := range week {
			day := weekStart.AddDate(0, 0, i)
			switch {
			case day.Before(start) || day.After(end):
				week[i] = "·"
			case day.Equal(today):
				week[i] = "◈"
			case day.Before(today):
				week[i] = "◼"
			default:
				week[i] = "◻"
			}
		}

		weekStr := weekStart.Format("Jan 02 ") + strings.Join(week, " ")
		if weekStart.AddDate(0, 0, 7).After(today) && !weekStart.After(today) {
			weekStr = underline + weekStr + reset
		}
		calendar = append(calendar, weekStr)
	}
	return strings.Join(calendar, "\n")
}

func getStatistics(today, start, end time.Time) string {
	totalDays := int(end.Sub(start).Hours()/24) + 1
	daysPassed := min(int(today.Sub(start).Hours()/24)+1, totalDays)
	daysRemaining := max(int(end.Sub(today).Hours()/24), 0)
	percentage := float64(daysPassed) / float64(totalDays)

	return fmt.Sprintf(
		"Days passed:    %3d (%.2f%%)\n"+
			"Days remaining: %3d (%.2f%%)\n"+
			"Total days:     %3d",
		daysPassed, percentage*100,
		daysRemaining, (1-percentage)*100,
		totalDays,
	)
}

func parseDate(s string) time.Time {
	t, err := time.Parse(time.DateOnly, s)
	if err != nil {
		fmt.Printf("Error parsing date: %v\n", err)
		os.Exit(1)
	}
	return t
}

func main() {
	if len(os.Args) != 3 || os.Args[1] == "-h" || os.Args[1] == "--help" {
		fmt.Println(`Usage: calendar <start_date> <end_date>

Show a calendar of the weeks between two dates. Dates should be in YYYY-MM-DD format.

Options:
  -h, --help    Display this help message`)
		os.Exit(1)
	}

	start, end := parseDate(os.Args[1]), parseDate(os.Args[2])
	if start.After(end) {
		fmt.Println("Error: End date must be after start date.")
		os.Exit(1)
	}

	today := time.Now().UTC().Truncate(24 * time.Hour)

	fmt.Println("From :", start.Format(time.DateOnly))
	fmt.Println("To   :", end.Format(time.DateOnly))
	fmt.Println("Today:", today.Format(time.DateOnly))
	fmt.Println()
	fmt.Println(generateCalendar(today, start, end))
	fmt.Println()
	fmt.Println(getStatistics(today, start, end))
}
