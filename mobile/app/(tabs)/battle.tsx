import { View, Text, Pressable, SectionList, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";

import { useBattles, type Battle } from "@/api/battles";
import { battleSummary, captureName, groupBattles, timeLeft } from "@/battles";

// Owner: Person C — Battle System
// The Battle tab: everything you are involved in, with the ones waiting on you at the
// top. Tapping a row opens the battle; the only action taken from this screen is starting
// a new one, because accept/decline needs to show the matchup first.

const STATUS_DOT: Record<string, string> = {
  pending: "bg-amber-400",
  resolving: "bg-amber-400",
  resolved: "bg-slate-300",
  declined: "bg-slate-300",
  expired: "bg-slate-300",
};

function BattleRow({ battle }: { battle: Battle }) {
  const countdown = timeLeft(battle.expires_at);
  const won = battle.outcome === "won";

  return (
    <Pressable
      onPress={() => router.push(`/battles/${battle.id}`)}
      className="mx-4 mb-2 flex-row items-center rounded-2xl border border-slate-200 bg-white p-3"
    >
      <View className={`mr-3 h-2 w-2 rounded-full ${STATUS_DOT[battle.status] ?? "bg-slate-300"}`} />

      <View className="flex-1">
        <Text className="font-semibold text-slate-900" numberOfLines={1}>
          {battleSummary(battle)}
        </Text>
        <Text className="text-xs text-slate-500" numberOfLines={1}>
          {/* The matchup, or just your side while the opponent has not picked. */}
          {captureName(battle.challenger.capture)}
          {battle.opponent.capture ? ` vs ${captureName(battle.opponent.capture)}` : ""}
        </Text>
      </View>

      <View className="ml-2 items-end">
        {battle.status === "resolved" ? (
          <>
            <Text className={`text-sm font-bold ${won ? "text-emerald-600" : "text-slate-400"}`}>
              {won ? "WON" : "LOST"}
            </Text>
            {/* Only the winner earned anything, and only if the payout actually went
                through — coins_awarded is null when it did not. */}
            {won && battle.coins_awarded ? (
              <Text className="text-xs text-emerald-600">+{battle.coins_awarded}</Text>
            ) : null}
          </>
        ) : countdown ? (
          <Text className="text-xs text-slate-400">{countdown}</Text>
        ) : null}
      </View>
    </Pressable>
  );
}

function SectionHeading({ title }: { title: string }) {
  return (
    <Text className="px-4 pb-2 pt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
      {title}
    </Text>
  );
}

function Centered({ title, detail, action }: { title: string; detail?: string; action?: React.ReactNode }) {
  return (
    <View className="flex-1 items-center justify-center px-8">
      <Text className="text-center text-base text-slate-700">{title}</Text>
      {detail ? <Text className="mt-2 text-center text-sm text-slate-400">{detail}</Text> : null}
      {action}
    </View>
  );
}

export default function BattleScreen() {
  const { data, isPending, isError, error, refetch, isRefetching } = useBattles();

  const groups = groupBattles(data ?? []);
  const sections = [
    // "Your turn" first and always, even when empty elsewhere: these are the only rows
    // with an action attached, and burying them under history is how a challenge sits
    // unanswered until it expires.
    { title: "Your turn", data: groups.incoming },
    { title: "Waiting on them", data: groups.outgoing },
    { title: "History", data: groups.finished },
  ].filter((s) => s.data.length > 0);

  const newBattle = (
    <Pressable
      onPress={() => router.push("/battle-challenge")}
      className="mt-4 rounded-full bg-slate-900 px-5 py-2"
    >
      <Text className="text-sm font-medium text-white">New battle</Text>
    </Pressable>
  );

  return (
    <SafeAreaView className="flex-1 bg-slate-50" edges={["top"]}>
      <View className="flex-row items-start justify-between px-4 pb-2 pt-3">
        <View>
          <Text className="text-2xl font-bold text-slate-900">Battle</Text>
          <Text className="text-sm text-slate-500">
            {isPending
              ? "Loading…"
              : groups.incoming.length > 0
                ? `${groups.incoming.length} waiting on you`
                : `${(data ?? []).length} battles`}
          </Text>
        </View>

        <Pressable
          onPress={() => router.push("/battle-challenge")}
          hitSlop={10}
          className="mt-1 rounded-full bg-slate-900 px-4 py-2"
        >
          <Text className="text-sm font-medium text-white">Challenge</Text>
        </Pressable>
      </View>

      {isPending ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator />
        </View>
      ) : isError ? (
        // Surfaced rather than swallowed: an empty list and a failed request look
        // identical, and only one of them is worth retrying.
        <Centered
          title="Couldn't load your battles."
          detail={error instanceof Error ? error.message : undefined}
          action={
            <Pressable onPress={() => refetch()} className="mt-4 rounded-full bg-slate-900 px-5 py-2">
              <Text className="text-sm font-medium text-white">Try again</Text>
            </Pressable>
          }
        />
      ) : sections.length === 0 ? (
        <Centered
          title="No battles yet."
          detail="Challenge another player with one of your captures."
          action={newBattle}
        />
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <BattleRow battle={item} />}
          renderSectionHeader={({ section }) => <SectionHeading title={section.title} />}
          onRefresh={refetch}
          refreshing={isRefetching}
          stickySectionHeadersEnabled={false}
          contentContainerStyle={{ paddingBottom: 24 }}
        />
      )}
    </SafeAreaView>
  );
}
