import { useState } from "react";
import { View, Text, Pressable, FlatList, ActivityIndicator, ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";

import { useChallenge, useOpponents, useRoster, type Opponent } from "@/api/battles";
import { BattleCard } from "@/battle/BattleCard";

// Owner: Person C — Battle System
// Starting a battle: choose who to fight, then what to fight with.
//
// Two steps on one screen rather than two routes. The opponent list is short and the
// roster is a grid, so both fit, and keeping them together means the player can change
// their mind about the opponent without losing their capture choice.
//
// Accepts an optional `opponentId` param so a future "challenge back" button on the
// result screen can deep-link straight to a chosen opponent.

function OpponentChip({
  opponent,
  selected,
  onPress,
}: {
  opponent: Opponent;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      className={`mr-2 rounded-2xl border-2 px-4 py-3 ${
        selected ? "border-slate-900 bg-slate-900" : "border-slate-200 bg-white"
      }`}
    >
      <Text className={`font-semibold ${selected ? "text-white" : "text-slate-900"}`}>
        {opponent.display_name}
      </Text>
      <Text className={`text-xs ${selected ? "text-slate-300" : "text-slate-500"}`}>
        {opponent.capture_count} {opponent.capture_count === 1 ? "capture" : "captures"}
      </Text>
    </Pressable>
  );
}

function Centered({ title, detail }: { title: string; detail?: string }) {
  return (
    <View className="flex-1 items-center justify-center px-8">
      <Text className="text-center text-base text-slate-700">{title}</Text>
      {detail ? <Text className="mt-2 text-center text-sm text-slate-400">{detail}</Text> : null}
    </View>
  );
}

export default function BattleChallengeScreen() {
  const params = useLocalSearchParams<{ opponentId?: string }>();
  const roster = useRoster();
  const opponents = useOpponents();
  const challenge = useChallenge();

  const [opponentId, setOpponentId] = useState<string | null>(params.opponentId ?? null);
  const [captureId, setCaptureId] = useState<string | null>(null);

  const captures = roster.data ?? [];
  const canSend = Boolean(opponentId && captureId) && !challenge.isPending;

  const send = () => {
    if (!opponentId || !captureId) return;
    challenge.mutate(
      { opponentId, captureId },
      {
        // Straight to the battle you just created, so the challenge is somewhere real
        // rather than a message that disappears. `replace` so Back returns to the Battle
        // tab instead of to a challenge form for a challenge already sent.
        onSuccess: (battle) => router.replace(`/battles/${battle.id}`),
      },
    );
  };

  const loading = roster.isPending || opponents.isPending;
  const failed = roster.isError || opponents.isError;

  return (
    <SafeAreaView className="flex-1 bg-slate-50" edges={["top"]}>
      <View className="flex-row items-center justify-between px-4 pb-2 pt-3">
        <Text className="text-2xl font-bold text-slate-900">New battle</Text>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <Text className="text-sm text-slate-500">Cancel</Text>
        </Pressable>
      </View>

      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator />
        </View>
      ) : failed ? (
        <Centered
          title="Couldn't load the battle setup."
          detail={
            roster.error instanceof Error
              ? roster.error.message
              : opponents.error instanceof Error
                ? opponents.error.message
                : undefined
          }
        />
      ) : captures.length === 0 ? (
        // You cannot fight with nothing. Sending the player to the camera is the only
        // useful thing this screen can do for them.
        <Centered
          title="You have no captures to battle with."
          detail="Photograph an animal on the Camera tab first."
        />
      ) : (opponents.data ?? []).length === 0 ? (
        <Centered
          title="Nobody to challenge yet."
          detail="Other players show up here once they've made a capture of their own."
        />
      ) : (
        <>
          <Text className="px-4 pb-2 pt-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Who
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="px-4">
            {(opponents.data ?? []).map((o) => (
              <OpponentChip
                key={o.user_id}
                opponent={o}
                selected={o.user_id === opponentId}
                onPress={() => setOpponentId(o.user_id)}
              />
            ))}
          </ScrollView>

          <Text className="px-4 pb-2 pt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
            With what
          </Text>
          <FlatList
            data={captures}
            keyExtractor={(item) => item.id}
            numColumns={3}
            contentContainerStyle={{ paddingHorizontal: 10, paddingBottom: 16 }}
            columnWrapperStyle={{ gap: 6 }}
            renderItem={({ item }) => (
              <View className="mb-1.5 flex-1">
                <BattleCard
                  capture={item}
                  selected={item.id === captureId}
                  onPress={() => setCaptureId(item.id)}
                />
              </View>
            )}
          />

          {/* The failure is shown here rather than thrown away: the most likely one is a
              409 for a challenge already outstanding against this player, which the
              player can act on by picking someone else. */}
          {challenge.isError ? (
            <Text className="px-4 pb-2 text-center text-sm text-rose-600">
              {challenge.error instanceof Error ? challenge.error.message : "Couldn't send the challenge."}
            </Text>
          ) : null}

          <Pressable
            disabled={!canSend}
            onPress={send}
            className={`mx-4 mb-4 items-center rounded-2xl p-4 ${canSend ? "bg-slate-900" : "bg-slate-300"}`}
          >
            <Text className="font-semibold text-white">
              {challenge.isPending
                ? "Sending…"
                : !opponentId
                  ? "Pick an opponent"
                  : !captureId
                    ? "Pick a capture"
                    : "Send challenge"}
            </Text>
          </Pressable>
        </>
      )}
    </SafeAreaView>
  );
}
