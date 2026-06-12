import axios, { AxiosError } from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": import.meta.env.VITE_INTERNAL_API_KEY,
  },
});

// 요청 인터셉터: 매 요청마다 인증 헤더 보장
client.interceptors.request.use(
  (config) => {
    config.headers["X-API-Key"] = import.meta.env.VITE_INTERNAL_API_KEY;
    return config;
  },
  (error) => Promise.reject(error)
);

// 응답 인터셉터: 공통 에러 처리 (백엔드 X-API-Key 미들웨어는 실패 시 401 반환)
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response) {
      const { status, data } = error.response;
      const reason = data?.detail ?? error.message;
      if (status === 401) {
        console.error(`[API] 인증 실패(401): ${reason}`);
      } else {
        console.error(`[API] 요청 실패(${status}): ${reason}`);
      }
    } else if (error.code === "ECONNABORTED") {
      console.error("[API] 요청 타임아웃");
    } else {
      console.error(`[API] 네트워크 오류: ${error.message}`);
    }
    return Promise.reject(error);
  }
);

export default client;
