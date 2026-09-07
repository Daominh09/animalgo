import { useState } from "react";
import { View, Text, Pressable, ScrollView, ActivityIndicator, FlatList } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";

import {
  useAcceptBattle,
  useBattle,
  useDeclineBattle,
  useRoster,
  type Battle,
} from "@/api/battles";
import { BattleCard } from "@/battle/BattleCard";
import { battleSummary, mySide, needsMyAnswer, theirSide, timeLeft, traitMatchup } from "@/battles";

// Owner: Person C — Battle System
// One battle: the matchup, the outcome once there is one, and the accept/decline choice
// while it is still yours to make.
//
// Accept lives here rather than on the Battle tab on purpose — answering a challenge
// means choosing which capture to answer with, and that choice needs to be made against
// the capture you are being challenged by.

function Centered({ title, detail, action }: { title: string; detail?: string; action?: React.ReactNode }) {
  return (
    <View className="flex-1 items-center justify-center px-8">
      <Text className="text-center text-base text-slate-700">{title}</Text>
      {detail ? <Text className="mt-2 text-center text-sm text-slate-400">{detail}</Text> : null}
      {action}
    </View>
  );
}

/** The two fighters side by side, with the score once the battle has been decided. */
function Matchup({ battle }: { battle: Battle }) {
  const mine = mySide(battle);
  const theirs = theirSide(battle);
  const resolved = battle.status === "resolved";

  return (
    <View className="flex-row items-start justify-center px-4">
      <View className="flex-1">
        <BattleCard capture={mine.capture} />
        <Text className="mt-1 text-center text-xs font-medium text-slate-500">You</Text>
        {resolved ? <Text className="text-center text-2xl font-bold text-slate-900">{mine.total}</Text> : null}
      </View>

      <View className="w-12 items-center pt-10">
        <Text className="text-sm font-bold text-slate-400">VS</Text>
      </View>

      <View className="flex-1">
        <BattleCard capture={theirs.capture} />
        <Text className="mt-1 text-center text-xs font-medium text-slate-500" numberOfLines={1}>
          {theirs.display_name}
        </Text>
        {resolved ? <Text className="text-center text-2xl font-bold text-slate-900">{theirs.total}</Text> : null}
      </View>
    </View>
  );
}

/** Why it went the way it did.
 *
 * Shown because a battle is otherwise two numbers appearing from nowhere. The roll is
 * what makes an upset explicable, and the trait line is what makes counterplay
 * learnable — a player who never sees that the trait mattered has no reason to build a
 * varied roster. */
function Breakdown({ battle }: { battle: Battle }) {
  const mine = mySide(battle);
  const theirs = theirSide(battle);
  const myAdvantage = battle.trait_advantage
    ? (battle.trait_advantage === "challenger") === (battle.role === "challenger")
    : null;

  return (
    <View className="mx-4 mt-6 rounded-2xl border border-slate-200 bg-white p-4">
      <Text className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        How it was decided
      </Text>

      <View className="flex-row justify-between py-1">
        <Text className="text-sm text-slate-600">Your roll</Text>
        <Text className="text-sm font-medium text-slate-900">{mine.roll}</Text>
      </View>
      <View className="flex-row justify-between py-1">
        <Text className="text-sm text-slate-600">{theirs.display_name}&apos;s roll</Text>
        <Text className="text-sm font-medium text-slate-900">{theirs.roll}</Text>
      </View>

      <View className="mt-2 border-t border-slate-100 pt-2">
        <Text className="text-sm text-slate-600">
          {myAdvantage === null
            ? "Neither trait had the edge."
            : myAdvantage
              ? "Your trait beat theirs — bonus to you."
              : `${theirs.display_name}'s trait beat yours — bonus to them.`}
        </Text>
      </View>
    </View>
  );
}

/** The roster picker shown when a challenge is waiting on you. */
function AnswerPanel({ battle }: { battle: Battle }) {
  const roster = useRoster();
  const accept = useAcceptBattle();
  const decline = useDeclineBattle();
  const [captureId, setCaptureId] = useState<string | null>(null);

  const captures = roster.data ?? [];
  const theirTrait = theirSide(battle).capture?.trait ?? null;
  const busy = accept.isPending || decline.isPending;
  const error = accept.error ?? decline.error;

  if (roster.isPending) {
    return (
      <View className="items-center py-8">
        <ActivityIndicator />
      </View>
    );
  }

  if (captures.length === 0) {
    return (
      <View className="px-4 py-8">
        <Text className="text-center text-sm text-slate-500">
          You have no captures to answer with. Photograph an animal on the Camera tab.
        </Text>
      </View>
    );
  }

  return (
    <View className="mt-6">
      <Text className="px-4 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Answer with
      </Text>

      <FlatList
        data={captures}
        keyExtractor={(item) => item.id}
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}
        renderItem={({ item }) => {
          // Shown before the choice is committed: seeing that a capture counters theirs
          // is the whole reason the trait cycle exists.
          const matchup = traitMatchup(item.trait, theirTrait);
          return (
            <View className="w-28">
              <BattleCard
                capture={item}
                selected={item.id === captureId}
                onPress={() => setCaptureId(item.id)}
              />
              {matchup ? (
                <Text
                  className={`mt-1 text-center text-[10px] font-medium ${
                    matchup === "advantage" ? "text-emerald-600" : "text-rose-500"
                  }`}
                >
                  {matchup === "advantage" ? "Counters theirs" : "Countered"}
                </Text>
              ) : null}
            </View>
          );
        }}
      />

      {error ? (
        <Text className="px-4 pt-3 text-center text-sm text-rose-600">
          {/* Most likely a 409: the challenge expired, or was already answered from
              another device. Worth reading rather than swallowing. */}
          {error instanceof Error ? error.message : "That didn't work."}
        </Text>
      ) : null}

      <View className="flex-row gap-3 px-4 pb-4 pt-4">
        <Pressable
          disabled={busy}
          onPress={() => decline.mutate({ battleId: battle.id })}
          className="flex-1 items-center rounded-2xl border border-slate-300 p-4"
        >
          <Text className="font-medium text-slate-600">
            {decline.isPending ? "Declining…" : "Decline"}
          </Text>
        </Pressable>

        <Pressable
          disabled={!captureId || busy}
          onPress={() => captureId && accept.mutate({ battleId: battle.id, captureId })}
          className={`flex-1 items-center rounded-2xl p-4 ${captureId && !busy ? "bg-slate-900" : "bg-slate-300"}`}
        >
          <Text className="font-semibold text-white">
            {accept.isPending ? "Fighting…" : captureId ? "Fight" : "Pick a capture"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

export default function BattleDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: battle, isPending, isError, error, refetch } = useBattle(id);

  const countdown = battle ? timeLeft(battle.expires_at) : null;
  const won = battle?.outcome === "won";

  return (
    <SafeAreaView className="flex-1 bg-slate-50" edges={["top"]}>
      <View className="flex-row items-center justify-between px-4 pb-2 pt-3">
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <Text className="text-sm text-slate-500">← Back</Text>
        </Pressable>
      </View>

      {isPending ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator />
        </View>
      ) : isError || !battle ? (
        <Centered
          title="Couldn't load this battle."
          detail={error instanceof Error ? error.message : undefined}
          action={
            <Pressable onPress={() => refetch()} className="mt-4 rounded-full bg-slate-900 px-5 py-2">
              <Text className="text-sm font-medium text-white">Try again</Text>
            </Pressable>
          }
        />
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 32 }}>
          <View className="items-center px-4 pb-6">
            {battle.status === "resolved" ? (
              <>
                <Text className={`text-3xl font-bold ${won ? "text-emerald-600" : "text-slate-400"}`}>
                  {won ? "You won!" : "You lost"}
                </Text>
                {/* coins_awarded is null when the payout failed, and the loser earns
                    nothing — in both cases there is no number to show, and inventing one
                    would tell the player they were paid when they were not. */}
                {won && battle.coins_awarded ? (
                  <Text className="mt-1 text-base font-medium text-emerald-600">
                    +{battle.coins_awarded} coins
                  </Text>
                ) : null}
              </>
            ) : (
              <>
                <Text className="text-xl font-bold text-slate-900">{battleSummary(battle)}</Text>
                {countdown ? <Text className="mt-1 text-sm text-slate-400">{countdown}</Text> : null}
              </>
            )}
          </View>

          <Matchup battle={battle} />

          {battle.status === "resolved" ? <Breakdown battle={battle} /> : null}

          {needsMyAnswer(battle) ? <AnswerPanel battle={battle} /> : null}

          {battle.status === "expired" ? (
            <Text className="px-8 pt-6 text-center text-sm text-slate-400">
              Nobody answered in time, so this challenge no longer counts.
            </Text>
          ) : null}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
