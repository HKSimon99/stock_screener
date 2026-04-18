import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  useWindowDimensions,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { fetchInstrument, fetchInstrumentChart } from '@consensus/api-client';
import { CandlestickChart, LineChart } from 'react-native-wagmi-charts';
import { CONVICTION_COLORS } from '@consensus/ui-tokens';

type Params = { market: 'US' | 'KR'; ticker: string };

export default function InstrumentDetailScreen() {
  const { market, ticker } = useLocalSearchParams<Params>();
  const { width } = useWindowDimensions();

  const { data: detail, isLoading: isLoadingDetail } = useQuery({
    queryKey: ['instrument', market, ticker],
    queryFn: () => fetchInstrument(ticker, market),
  });

  const { data: chart, isLoading: isLoadingChart } = useQuery({
    queryKey: ['chart', market, ticker],
    queryFn: () =>
      fetchInstrumentChart(ticker, market, { range_days: 180, interval: '1d' }),
  });

  if (isLoadingDetail || isLoadingChart) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#0f172a" />
      </View>
    );
  }

  if (!detail || !chart) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Instrument not found.</Text>
      </View>
    );
  }

  // Format chart data for wagmi-charts
  const candleData = chart.bars.map((b) => ({
    timestamp: new Date(b.time).getTime(),
    open: b.open,
    high: b.high,
    low: b.low,
    close: b.close,
  }));

  const rsLineData = chart.rs_line.map((pt) => ({
    timestamp: new Date(pt.time).getTime(),
    value: pt.value,
  }));

  const { piotroski_detail, minervini_detail, weinstein_detail } = detail;

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.ticker}>{detail.ticker}</Text>
          <Text style={styles.name}>{detail.name}</Text>
        </View>
        <View style={styles.badgeContainer}>
          <View
            style={[
              styles.badge,
              { backgroundColor: CONVICTION_COLORS[detail.conviction_level] || '#e2e8f0' },
            ]}
          >
            <Text style={styles.badgeText}>{detail.conviction_level}</Text>
          </View>
          <Text style={styles.scoreText}>{detail.final_score.toFixed(1)}</Text>
        </View>
      </View>

      {/* Chart Section */}
      <View style={styles.chartSection}>
        {candleData.length > 0 ? (
          <CandlestickChart.Provider data={candleData}>
            <CandlestickChart height={250} width={width}>
              <CandlestickChart.Candles />
              <CandlestickChart.Crosshair />
            </CandlestickChart>
          </CandlestickChart.Provider>
        ) : (
          <Text style={styles.noDataText}>No price data available.</Text>
        )}
      </View>

      {/* Strategy Scorecard Section */}
      <View style={styles.scorecard}>
        <Text style={styles.sectionTitle}>Strategy Scorecard</Text>

        {/* Piotroski */}
        <View style={styles.cardBlock}>
          <Text style={styles.cardTitle}>Piotroski F-Score</Text>
          <Text style={styles.cardValue}>{piotroski_detail?.f_score ?? 0}/9</Text>
        </View>

        {/* Minervini */}
        <View style={styles.cardBlock}>
          <Text style={styles.cardTitle}>Minervini Trend Template</Text>
          <Text style={styles.cardValue}>
            {minervini_detail?.count_passing ?? 0}/8 Criteria
          </Text>
        </View>

        {/* Weinstein */}
        <View style={styles.cardBlock}>
          <Text style={styles.cardTitle}>Weinstein Stage</Text>
          <Text style={styles.cardValue}>Stage {weinstein_detail?.stage ?? '-'}</Text>
        </View>
      </View>
    </ScrollView>
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
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  ticker: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#0f172a',
  },
  name: {
    fontSize: 14,
    color: '#64748b',
  },
  badgeContainer: {
    alignItems: 'flex-end',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    marginBottom: 4,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#0f172a',
  },
  scoreText: {
    fontSize: 20,
    fontWeight: '900',
    color: '#0f172a',
  },
  chartSection: {
    backgroundColor: '#fff',
    marginVertical: 16,
    paddingVertical: 16,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: '#e2e8f0',
  },
  noDataText: {
    textAlign: 'center',
    color: '#64748b',
    padding: 20,
  },
  scorecard: {
    padding: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 12,
    color: '#0f172a',
  },
  cardBlock: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  cardTitle: {
    fontSize: 16,
    color: '#334155',
    fontWeight: '600',
  },
  cardValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#0f172a',
  },
  errorText: {
    fontSize: 16,
    color: '#ef4444',
  },
});
