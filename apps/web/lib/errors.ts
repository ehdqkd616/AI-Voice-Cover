// §7.2 error codes → user-facing Korean text. Falls back to the raw
// (often English) message for codes not listed here.
const ERROR_MESSAGES: Record<string, string> = {
  DRM_PROTECTED: "이 영상은 DRM으로 보호되어 있어 다운로드할 수 없습니다.",
  VIDEO_UNAVAILABLE: "더 이상 볼 수 없는 영상입니다 (비공개 처리되었거나 삭제됨).",
  AGE_RESTRICTED: "연령 제한이 걸린 영상이라 처리할 수 없습니다.",
  GEO_BLOCKED: "현재 지역에서는 볼 수 없는 영상입니다.",
  LIVE_STREAM_UNSUPPORTED: "라이브 스트림은 처리할 수 없습니다.",
  VIDEO_TOO_LONG: "영상이 너무 깁니다.",
  INVALID_URL: "유효한 유튜브 URL이 아닙니다.",
  RATE_LIMITED: "일일 사용 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
  DOWNLOAD_TEMPORARILY_DISABLED: "유튜브 다운로드 기능이 일시적으로 비활성화되었습니다.",
  EXTRACTION_FAILED: "추출에 실패했습니다. 다른 영상으로 시도하거나 잠시 후 다시 시도해주세요.",
  GPU_OOM: "처리 중 메모리 부족이 발생했습니다. 잠시 후 다시 시도해주세요.",
  EMAIL_TAKEN: "이미 가입된 이메일입니다.",
  INVALID_CREDENTIALS: "이메일 또는 비밀번호가 올바르지 않습니다.",
  NOT_AUTHENTICATED: "로그인이 필요합니다.",
  PENDING_APPROVAL: "관리자 승인 대기 중입니다.",
  FORBIDDEN: "관리자만 접근할 수 있습니다.",
  NOT_FOUND: "요청한 항목을 찾을 수 없습니다.",
  VALIDATION_ERROR: "입력값을 확인해주세요.",
  UNSUPPORTED_FORMAT: "지원하지 않는 파일 형식입니다.",
  FILE_TOO_LARGE: "파일이 너무 큽니다.",
  QUEUE_FULL: "현재 대기열이 가득 찼습니다. 잠시 후 다시 시도해주세요.",
  VOICE_MODEL_NOT_FOUND: "선택한 보이스 모델을 더 이상 사용할 수 없습니다. 다른 모델을 선택해주세요.",
};

export function translateError(code: string | undefined | null, fallback?: string | null): string {
  if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
  return fallback ?? "작업이 실패했습니다.";
}
