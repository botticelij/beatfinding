library(tidyverse)

# Step 1: Expand the resp_onsets_detected column into long format
data_tapmusic_long <- data_tapmusic %>%
  select(participant_id, id, resp_onsets_detected) %>%
  mutate(resp_onsets_detected = map(resp_onsets_detected, ~ as.numeric(str_split(.x, ",", simplify = TRUE)))) %>%
  unnest(resp_onsets_detected) %>%
  mutate(resp_onsets_detected = as.numeric(resp_onsets_detected))

# Step 2: Plot
ggplot(data_tapmusic_long, aes(x = resp_onsets_detected, y = factor(participant_id))) +
  geom_point(alpha = 0.7) +
  labs(
    title = "Tapping onsets across participants",
    x = "Time (ms)",
    y = "Participant ID"
  ) +
  theme_minimal()

ggplot(data_tapmusic_long, aes(x = resp_onsets_detected)) +
  geom_density(fill = "blue", alpha = 0.3) +
  labs(
    title = "Density of tapping onsets across all trials",
    x = "Time (ms)",
    y = "Density"
  ) +
  theme_minimal()

ggplot(data_tapmusic_long, aes(x = resp_onsets_detected)) +
  geom_histogram(binwidth = 200, fill = "darkgreen", alpha = 0.6) +
  facet_wrap(~ participant_id, scales = "free_y") +
  labs(
    title = "Histogram of tap times by participant",
    x = "Time (ms)",
    y = "Count"
  ) +
  theme_minimal()

library(jsonlite)
library(tidyverse)

# Parse the JSON string from the `output` column to extract "tapping_detected_onsets"
data_output_onsets <- data_tapmusic %>%
  select(participant_id, id, output) %>%
  mutate(
    parsed_output = map(output, ~ fromJSON(.x)),
    tapping_onsets = map(parsed_output, "tapping_detected_onsets")
  ) %>%
  unnest(tapping_onsets) %>%
  mutate(tapping_onsets = as.numeric(tapping_onsets))



