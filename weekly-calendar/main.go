package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
	"time"
	"unicode"
)

const (
	underline = "\033[4m"
	bold      = "\033[1m"
	reset     = "\033[0m"
)

// isVacationDay checks if a given day is within the vacation period.
func isVacationDay(day, vacationStart, vacationEnd time.Time) bool {
	return !day.Before(vacationStart) && !day.After(vacationEnd)
}

// generateCalendar creates a slice of strings representing each week in the calendar.
// It excludes vacation days from highlighting and does not count them in the calendar.
func generateCalendar(today, start, end, vacationStart, vacationEnd time.Time) []string {
	var calendar []string
	for current := start; !current.After(end); current = current.AddDate(0, 0, 7) {
		week := make([]string, 7)
		// Week starts on Monday
		weekStart := current.AddDate(0, 0, -int(current.Weekday())+1)

		for i := range week {
			day := weekStart.AddDate(0, 0, i)
			// Check if the day is within the vacation period
			if !vacationStart.IsZero() && !vacationEnd.IsZero() &&
				isVacationDay(day, vacationStart, vacationEnd) {
				week[i] = "V" // Represent vacation days with "V"
				continue
			}
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
		// Apply underline to the week containing today, excluding vacation weeks
		if !vacationStart.IsZero() && !vacationEnd.IsZero() {
			if weekStart.AddDate(0, 0, 7).After(today) && !weekStart.After(today) &&
				!isVacationDay(weekStart, vacationStart, vacationEnd) &&
				!isVacationDay(weekStart.AddDate(0, 0, 6), vacationStart, vacationEnd) {
				weekStr = underline + weekStr + reset
			}
		} else {
			if weekStart.AddDate(0, 0, 7).After(today) && !weekStart.After(today) {
				weekStr = underline + weekStr + reset
			}
		}
		calendar = append(calendar, weekStr)
	}
	return calendar
}

// getStatistics calculates and returns the statistics string, excluding vacation days.
func getStatistics(today, start, end, vacationStart, vacationEnd time.Time) string {
	totalDays := 0
	daysPassed := 0
	daysRemaining := 0

	for day := start; !day.After(end); day = day.AddDate(0, 0, 1) {
		// Skip vacation days
		if !vacationStart.IsZero() && !vacationEnd.IsZero() &&
			isVacationDay(day, vacationStart, vacationEnd) {
			continue
		}
		totalDays++
		if !day.After(today) {
			daysPassed++
		} else {
			daysRemaining++
		}
	}

	percentage := 0.0
	if totalDays > 0 {
		percentage = float64(daysPassed) / float64(totalDays)
	}

	return fmt.Sprintf(
		"Days passed:    %3d (%.2f%%)\n"+
			"Days remaining: %3d (%.2f%%)\n"+
			"Total days:     %3d",
		daysPassed, percentage*100,
		daysRemaining, (1-percentage)*100,
		totalDays,
	)
}

// parseDate parses a date string in YYYY-MM-DD format.
func parseDate(s string) time.Time {
	t, err := time.Parse("2006-01-02", s)
	if err != nil {
		fmt.Printf("Error parsing date '%s': %v\n", s, err)
		os.Exit(1)
	}
	return t
}

// readTodoList reads the todo list from the specified file path.
func readTodoList(path string) ([]string, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("Error reading todo file '%s': %w\n", path, err)
	}

	lines := []string{}
	for _, line := range strings.Split(string(content), "\n") {
		line = strings.TrimRightFunc(line, unicode.IsSpace)
		if line != "" {
			lines = append(lines, line)
		}
	}

	return lines, nil
}

func main() {
	todoPath := flag.String("todo", "", "Path to the todo list file")
	vacationStartStr := flag.String(
		"vacation-start",
		"",
		"Start date of vacation in YYYY-MM-DD format",
	)
	vacationEndStr := flag.String("vacation-end", "", "End date of vacation in YYYY-MM-DD format")

	flag.Usage = func() {
		fmt.Println(`Usage: weekly-calendar [options] <start_date> <end_date>

Show a calendar of the weeks between two dates along with a todo list. Dates should be in YYYY-MM-DD format.

Options:
  --todo string
        Path to the todo list file (default "")
  --vacation-start string
        Start date of vacation in YYYY-MM-DD format
  --vacation-end string
        End date of vacation in YYYY-MM-DD format
  -h, --help
        Display this help message`)
		os.Exit(0)
	}
	flag.Parse()

	if flag.NArg() != 2 {
		fmt.Println("Error: Please provide start and end dates in YYYY-MM-DD format.")
		fmt.Println("Use -h or --help for usage information.")
		os.Exit(1)
	}

	start, end := parseDate(flag.Arg(0)), parseDate(flag.Arg(1))
	if start.After(end) {
		fmt.Println("Error: End date must be after start date.")
		os.Exit(1)
	}

	var vacationStart, vacationEnd time.Time
	if (*vacationStartStr != "" && *vacationEndStr == "") ||
		(*vacationStartStr == "" && *vacationEndStr != "") {
		fmt.Println("Error: Both --vacation-start and --vacation-end must be provided together.")
		os.Exit(1)
	}
	if *vacationStartStr != "" && *vacationEndStr != "" {
		vacationStart = parseDate(*vacationStartStr)
		vacationEnd = parseDate(*vacationEndStr)
		if vacationStart.After(vacationEnd) {
			fmt.Println("Error: Vacation start date must be before or equal to vacation end date.")
			os.Exit(1)
		}
		// Ensure vacation is within the start and end dates
		if vacationStart.Before(start) || vacationEnd.After(end) {
			fmt.Println("Error: Vacation period must be within the start and end dates.")
			os.Exit(1)
		}
	}

	today := time.Now().UTC().Truncate(24 * time.Hour)

	fmt.Println(bold + underline + "Weekly Calendar:" + reset)
	fmt.Printf("From : %s\n", start.Format("2006-01-02"))
	fmt.Printf("To   : %s\n", end.Format("2006-01-02"))
	fmt.Printf("Today: %s\n\n", today.Format("2006-01-02"))

	// Add Vacations section if vacation dates are provided
	if !vacationStart.IsZero() && !vacationEnd.IsZero() {
		fmt.Println(underline + "Vacations:" + reset)
		fmt.Printf(
			"- %s to %s\n\n",
			vacationStart.Format("2006-01-02"),
			vacationEnd.Format("2006-01-02"),
		)
	}

	calendar := generateCalendar(today, start, end, vacationStart, vacationEnd)
	for _, line := range calendar {
		fmt.Println(line)
	}
	fmt.Println()
	fmt.Println(getStatistics(today, start, end, vacationStart, vacationEnd))

	if *todoPath != "" {
		todos, err := readTodoList(*todoPath)
		if err != nil {
			fmt.Printf("Error reading todo file '%s': %v\n", *todoPath, err)
			os.Exit(1)
		}

		fmt.Println(bold + underline + "\nTodo List:" + reset)
		for _, todo := range todos {
			fmt.Println(todo)
		}
	}
}
