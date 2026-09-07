import { Pressable, ScrollView, Text, View } from "react-native";

import type { SpeciesFilter, SpeciesOption } from "./mapHtml";

interface Props {
  options: SpeciesOption[];
  selected: SpeciesFilter;
  total: number;
  onSelect: (speciesId: SpeciesFilter) => void;
}

/** Compact single-select chips shared by the native and web maps. */
export function SpeciesFilterBar({ options, selected, total, onSelect }: Props) {
  if (options.length === 0) return null;

  return (
    <View className="mt-2">
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ gap: 8, paddingHorizontal: 12 }}
        accessibilityRole="radiogroup"
      >
        <FilterChip
          label="All species"
          count={total}
          selected={selected === undefined}
          onPress={() => onSelect(undefined)}
        />
        {options.map((option) => (
          <FilterChip
            key={option.id === null ? "species:null" : `species:${option.id}`}
            label={option.label}
            count={option.count}
            selected={selected === option.id}
            onPress={() => onSelect(option.id)}
          />
        ))}
      </ScrollView>
    </View>
  );
}

interface ChipProps {
  label: string;
  count: number;
  selected: boolean;
  onPress: () => void;
}

function FilterChip({ label, count, selected, onPress }: ChipProps) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ checked: selected }}
      accessibilityLabel={`${label}, ${count} ${count === 1 ? "capture" : "captures"}`}
      onPress={onPress}
      className={`rounded-full border px-3 py-2 ${
        selected ? "border-teal-700 bg-teal-700" : "border-slate-200 bg-white"
      }`}
      style={({ pressed }) => ({ opacity: pressed ? 0.75 : 1 })}
    >
      <Text className={`text-xs font-semibold ${selected ? "text-white" : "text-slate-700"}`}>
        {label} · {count}
      </Text>
    </Pressable>
  );
}
