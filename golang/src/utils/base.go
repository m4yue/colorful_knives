package utils

func Unique(target []string) []string {
	if len(target) == 0 {
		return target
	}

	uniqueSet := make(map[string]bool)

	for _, item := range target {
		uniqueSet[item] = true
	}

	result := make([]string, 0)
	for k, _ := range uniqueSet {
		result = append(result, k)
	}

	return result
}
