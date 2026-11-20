// @ts-nocheck
'use client';
// 로그인하지 않은 방문자에게 보여 주는 서비스 소개 홈 화면.
// 내용은 아래 LANDING 객체만 고치면 된다. 스타일은 landing.css(.lp- 접두사)에만 있다.
import './landing.css';

export const LANDING = {
  "icon": "🎙️",
  "name": "AI Voice Cover",
  "tagline": "노래와 목소리 모델만 고르면 AI 커버곡이 완성돼요",
  "intro": "음원 파일이나 유튜브 링크를 넣고 목소리를 고르면, 보컬 분리부터 목소리 변환, 반주 합치기까지 서버가 자동으로 처리해요.",
  "access": "회원가입 후 관리자 승인을 받으면 사용할 수 있어요.",
  "features": [
    {
      "icon": "🔗",
      "title": "파일·유튜브 지원",
      "desc": "음원 파일을 올리거나 유튜브 주소만 붙여 넣으면 돼요."
    },
    {
      "icon": "🎛️",
      "title": "보컬 / 반주 분리",
      "desc": "AI(Demucs)로 노래에서 목소리와 반주를 깨끗하게 나눠요."
    },
    {
      "icon": "🗣️",
      "title": "목소리 변환 (RVC)",
      "desc": "분리한 보컬을 고른 목소리 모델로 바꿔 불러 줘요."
    },
    {
      "icon": "🎧",
      "title": "자동 믹스·다운로드",
      "desc": "변환된 보컬과 반주를 다시 합쳐 완성된 커버곡을 내려받아요."
    }
  ],
  "steps": [
    "회원가입하고 관리자 승인을 기다려요.",
    "원곡 파일이나 유튜브 링크를 넣어요.",
    "목소리 모델을 고르면 커버곡이 만들어져요."
  ]
};

export default function Landing({ LinkComponent, loginHref = '/login', signupHref = '/signup', className = '', accent }: { LinkComponent?: any; loginHref?: string; signupHref?: string; className?: string; accent?: string }) {
  const L = LinkComponent ?? ((p) => <a href={p.to} className={p.className}>{p.children}</a>);
  const d = LANDING;
  return (
    <div className={`lp ${className}`} style={accent ? { '--lp-accent': accent, '--lp-accent-text': '#0f0f14' } : undefined}>
      <section className="lp-hero">
        <div className="lp-icon" aria-hidden="true">{d.icon}</div>
        <h1 className="lp-title">{d.name}</h1>
        <p className="lp-tagline">{d.tagline}</p>
        {d.intro && <p className="lp-intro">{d.intro}</p>}
        <div className="lp-cta">
          <L to={loginHref} className="lp-btn lp-btn-primary">로그인</L>
          {signupHref && <L to={signupHref} className="lp-btn">{d.signupLabel ?? '회원가입'}</L>}
        </div>
        {d.access && <p className="lp-access">{d.access}</p>}
      </section>

      <section className="lp-section">
        <h2 className="lp-h2">이런 걸 할 수 있어요</h2>
        <ul className="lp-features">
          {d.features.map((f) => (
            <li key={f.title} className="lp-feature">
              <span className="lp-feature-icon" aria-hidden="true">{f.icon}</span>
              <div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {d.steps?.length > 0 && (
        <section className="lp-section">
          <h2 className="lp-h2">사용 방법</h2>
          <ol className="lp-steps">
            {d.steps.map((s) => <li key={s}>{s}</li>)}
          </ol>
        </section>
      )}

      <footer className="lp-footer">
        <a href="https://multi-tools.hotgarlic.dedyn.io">다른 프로젝트 둘러보기 →</a>
      </footer>
    </div>
  );
}
