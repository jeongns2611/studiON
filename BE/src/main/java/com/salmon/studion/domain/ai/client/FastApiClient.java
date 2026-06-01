package com.salmon.studion.domain.ai.client;

import com.salmon.studion.domain.ai.dto.request.AiJobStartRequest;
import com.salmon.studion.domain.ai.dto.request.AiUserFeedbackRequest;
import com.salmon.studion.domain.ai.dto.response.AiJobStartResponse;
import com.salmon.studion.domain.ai.dto.response.AiWorkflowJobResponse;
import com.salmon.studion.domain.ai.dto.response.AiWorkflowStatusResponse;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

@Component
@Slf4j
@RequiredArgsConstructor
public class FastApiClient {

    private final WebClient aiWebClient;

    // AI 워크플로우 시작 요청 api
    public AiJobStartResponse startWorkflow(AiJobStartRequest request) {
        log.info("FastAPI workflow start 호출 | jobId={} projectId={}", request.getJobId(), request.getProjectId());
        return aiWebClient.post()
                .uri("/internal/workflow/jobs/start")
                .bodyValue(request)
                .retrieve()
                .onStatus(HttpStatusCode::isError, response ->
                        response.bodyToMono(String.class)
                                .map(body -> {
                                    log.error("FastAPI workflow start 호출 실패 | body={}", body);
                                    return new BusinessException(ErrorCode.AI_FASTAPI_CALL_FAILED);
                                }))
                .bodyToMono(AiJobStartResponse.class)
                .block();
    }

    // AI 워크플로우 상태 조회 api
    public AiWorkflowStatusResponse getWorkflowStatus(Integer jobId) {
        log.info("FastAPI workflow status 조회 | jobId={}", jobId);
        return aiWebClient.get()
                .uri("/internal/workflow/jobs/{jobId}", jobId)
                .retrieve()
                .onStatus(HttpStatusCode::isError, response ->
                        response.bodyToMono(String.class)
                                .map(body -> {
                                    log.error("FastAPI workflow status 조회 실패 | jobId={} body={}", jobId, body);
                                    return new BusinessException(ErrorCode.AI_FASTAPI_CALL_FAILED);
                                }))
                .bodyToMono(AiWorkflowStatusResponse.class)
                .block();
    }

    // 사용자 피드백 입력 API
    // 작업이 fastapi에 전달이 됐는지 안됐는지만 리턴해줌.
    public AiWorkflowJobResponse dispatchUserFeedback(AiUserFeedbackRequest request) {

        log.info("FastAPI user feedback 호출 | jobId={} projectId={}", request.getJobId(), request.getProjectId());

        return aiWebClient.post()
                .uri("/internal/workflow/jobs/{jobId}/feedback", request.getJobId())
                .bodyValue(request)
                .retrieve()
                .onStatus(HttpStatusCode::isError, response ->
                        response.bodyToMono(String.class)
                                .map(body -> {
                                    log.error("FastAPI user feedback 전달 실패 | jobId = {} projectId={} body={}", request.getJobId(), request.getProjectId(), body);
                                    return new BusinessException(ErrorCode.AI_FASTAPI_CALL_FAILED);
                                }))
                .bodyToMono(AiJobStartResponse.class)
                .map(AiJobStartResponse::getJob)
                .block();


    }
}
