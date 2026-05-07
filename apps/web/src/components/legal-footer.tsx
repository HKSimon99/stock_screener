import Link from "next/link";

/**
 * LegalFooter — 투자 정보 제공 고지 (법적 면책)
 * 모든 페이지 하단에 표시. 투자자문업 면책 조항.
 */
export function LegalFooter() {
  return (
    <footer className="app-shell mt-8 pb-28 md:pb-10">
      <div className="surface-panel rounded-xl px-5 py-4">
        <p className="text-[0.72rem] leading-relaxed text-[var(--rv-mute)]">
          <span className="font-semibold text-[var(--rv-ink)]">투자 정보 제공 목적</span>
          &nbsp;- 본 서비스는 CANSLIM·Piotroski·Magic Formula 등 공개된 투자 방법론을
          기반으로 주식 정보를 점수화·순위화하여 제공하는 정보 서비스입니다.
          투자 권유, 매매 추천 또는 투자 자문에 해당하지 않습니다.
          모든 투자 결정은 이용자 본인의 판단과 책임 하에 이루어져야 하며,
          서비스 제공자는 투자 결과에 대한 책임을 지지 않습니다.
          &nbsp;
          <Link href="/disclosures" className="inline-flex min-h-6 items-center font-semibold text-[var(--rv-primary)] underline-offset-2 hover:underline">
            상세 고지 보기
          </Link>
        </p>
      </div>
    </footer>
  );
}
