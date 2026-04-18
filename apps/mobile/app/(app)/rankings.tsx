import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { Stack, useRouter } from 'expo-router';
import { fetchRankings, RankingItem } from '@consensus/api-client';
import { CONVICTION_COLORS } from '@consensus/ui-tokens';

type Market = 'US' | 'KR';

export default function RankingsScreen() {
  const [market, setMarket] = useState<Market>('US');
  const router = useRouter();

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ['rankings', market],
    queryFn: () => fetchRankings({ market, limit: 50 }),
  });

  const renderItem = ({ item }: { item: RankingItem }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push(`/instrument/${market}/${item.ticker}`)}
    >
      <View style={styles.cardHeader}>
        <View>
          <Text style={styles.ticker}>{item.ticker}</Text>
          <Text style={styles.name} numberOfLines={1}>
            {item.name || 'Unknown'}
          </Text>
        </View>
        <View style={styles.scoreContainer}>
          <Text style={styles.scoreLabel}>Score</Text>
          <Text style={styles.scoreValue}>{item.final_score.toFixed(1)}</Text>
        </View>
      </View>
      <View style={styles.cardFooter}>
        <View
          style={[
            styles.badge,
            { backgroundColor: CONVICTION_COLORS[item.conviction_level] || '#e2e8f0' },
          ]}
        >
          <Text style={styles.badgeText}>{item.conviction_level}</Text>
        </View>
        <Text style={styles.dateText}>
          Strategy Passes: {item.strategy_pass_count}/5
        </Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          title: 'Rankings',
          headerRight: () => (
            <TouchableOpacity
              onPress={() => setMarket((prev) => (prev === 'US' ? 'KR' : 'US'))}
              style={styles.marketToggle}
            >
              <Text style={styles.marketToggleText}>{market}</Text>
            </TouchableOpacity>
          ),
        }}
      />

      {isLoading && !isRefetching ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#0f172a" />
        </View>
      ) : isError ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>Failed to load rankings.</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => refetch()}>
            <Text style={styles.retryBtnText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={data?.items || []}
          keyExtractor={(item) => item.instrument_id.toString()}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={isRefetching} onRefresh={refetch} />
          }
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.emptyText}>No consensus scores found.</Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  listContent: {
    padding: 16,
  },
  marketToggle: {
    backgroundColor: '#0f172a',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
  },
  marketToggleText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  ticker: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#0f172a',
  },
  name: {
    fontSize: 14,
    color: '#64748b',
    maxWidth: 200,
  },
  scoreContainer: {
    alignItems: 'flex-end',
  },
  scoreLabel: {
    fontSize: 12,
    color: '#64748b',
    textTransform: 'uppercase',
  },
  scoreValue: {
    fontSize: 20,
    fontWeight: '900',
    color: '#0f172a',
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#0f172a',
  },
  dateText: {
    fontSize: 12,
    color: '#64748b',
  },
  errorText: {
    fontSize: 16,
    color: '#ef4444',
    marginBottom: 12,
  },
  emptyText: {
    fontSize: 16,
    color: '#64748b',
  },
  retryBtn: {
    backgroundColor: '#0f172a',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryBtnText: {
    color: '#fff',
    fontWeight: '600',
  },
});
