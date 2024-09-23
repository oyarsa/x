package main

import (
	"fmt"
	"os"
	"strings"
	"time"
)

// ANSI escape codes
const (
	UNDERLINE = "\033[4m"
	RESET     = "\033[0m"
)

func generateCalendar(today, startDate, endDate time.Time) string {
	current := startDate
	var calendar []string

	for current.Before(endDate) || current.Equal(endDate) {
		week := make([]string, 7)
		weekStart := current.AddDate(0, 0, -int(current.Weekday())+1)

		for i := range week {
			day := weekStart.AddDate(0, 0, i)
			if day.Before(startDate) || day.After(endDate) {
				week[i] = "·"
			} else {
				switch {
				case day.Equal(today):
					week[i] = "◈"
				case day.Before(today):
					week[i] = "◼"
				default:
					week[i] = "◻"
				}
			}
		}

		weekStr := weekStart.Format("Jan 02 ") + strings.Join(week, " ")

		if (weekStart.Before(today) || weekStart.Equal(today)) &&
			today.Before(weekStart.AddDate(0, 0, 7)) {
			calendar = append(calendar, UNDERLINE+weekStr+RESET)
		} else {
			calendar = append(calendar, weekStr)
		}

		current = current.AddDate(0, 0, 7)
	}

	return strings.Join(calendar, "\n")
}

func getStatistics(today, startDate, endDate time.Time) string {
	totalDays := int(endDate.Sub(startDate).Hours()/24) + 1

	daysPassed := int(today.Sub(startDate).Hours()/24) + 1
	if today.After(endDate) {
		daysPassed = totalDays
	}

	daysRemaining := int(endDate.Sub(today).Hours() / 24)
	if daysRemaining < 0 {
		daysRemaining = 0
	}

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

func main() {
	if len(os.Args) != 3 || os.Args[1] == "-h" || os.Args[1] == "--help" {
		fmt.Println("Usage: calendar <start_date> <end_date>")
		fmt.Println("\nDates should be in YYYY-MM-DD format")
		os.Exit(1)
	}
	startDateStr := os.Args[1]
	endDateStr := os.Args[2]

	startDate, err := time.Parse(time.DateOnly, startDateStr)
	if err != nil {
		fmt.Printf("Error parsing start date: %v\n", err)
		os.Exit(1)
	}

	endDate, err := time.Parse(time.DateOnly, endDateStr)
	if err != nil {
		fmt.Printf("Error parsing end date: %v\n", err)
		os.Exit(1)
	}

	if startDate.After(endDate) {
		fmt.Println("Error: End date must be after start date.")
		os.Exit(1)
	}

	now := time.Now().UTC()
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())

	fmt.Println("From :", startDateStr)
	fmt.Println("To   :", endDateStr)
	fmt.Println("Today:", today.Format(time.DateOnly))
	fmt.Println()
	fmt.Println(generateCalendar(today, startDate, endDate))
	fmt.Println()
	fmt.Println(getStatistics(today, startDate, endDate))
}
