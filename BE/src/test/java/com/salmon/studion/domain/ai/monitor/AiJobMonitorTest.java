// package com.salmon.studion.domain.ai.monitor;

// import com.salmon.studion.domain.ai.client.FastApiClient;
// import com.salmon.studion.domain.ai.dto.response.AiWorkflowJobStatusResponse;
// import com.salmon.studion.domain.ai.dto.response.AiWorkflowStatusResponse;
// import com.salmon.studion.domain.ai.entity.AiAnalysisJob;
// import com.salmon.studion.domain.ai.repository.AiAnalysisJobRepository;
// import com.salmon.studion.domain.ai.websocket.AiJobEventPublisher;
// import org.junit.jupiter.api.DisplayName;
// import org.junit.jupiter.api.Test;
// import org.junit.jupiter.api.extension.ExtendWith;
// import org.mockito.InjectMocks;
// import org.mockito.Mock;
// import org.mockito.junit.jupiter.MockitoExtension;
// import org.springframework.scheduling.TaskScheduler;
// import org.springframework.test.util.ReflectionTestUtils;

// import java.util.Optional;

// import static org.assertj.core.api.Assertions.assertThat;
// import static org.mockito.Mockito.never;
// import static org.mockito.Mockito.verify;
// import static org.mockito.Mockito.when;

// @ExtendWith(MockitoExtension.class)
// class AiJobMonitorTest {

//     @Mock
//     private FastApiClient fastApiClient;

//     @Mock
//     private TaskScheduler taskScheduler;

//     @Mock
//     private AiJobEventPublisher aiJobEventPublisher;

//     @Mock
//     private AiAnalysisJobRepository aiAnalysisJobRepository;

//     @InjectMocks
//     private AiJobMonitor aiJobMonitor;

//     @Test
//     @DisplayName("폴링 상태 변화가 ai_analysis_job row에 동기화되고 websocket 이벤트가 발행된다")
//     void pollSyncsJobSnapshotAndPublishesStatusEvent() {
//         AiAnalysisJob job = AiAnalysisJob.create(4100, 81);
//         ReflectionTestUtils.setField(job, "id", 8100);
//         when(aiAnalysisJobRepository.findById(8100)).thenReturn(Optional.of(job));

//         AiWorkflowStatusResponse response = buildStatusResponse(
//                 8100,
//                 4100,
//                 "COMPLETED",
//                 "completed",
//                 100,
//                 "sync-finished"
//         );
//         when(fastApiClient.getWorkflowStatus(8100)).thenReturn(response);

//         ReflectionTestUtils.invokeMethod(aiJobMonitor, "poll", 8100, 4100);

//         assertThat(job.getStatus()).isEqualTo("COMPLETED");
//         assertThat(job.getPhase()).isEqualTo("completed");
//         assertThat(job.getProgress()).isEqualTo(100);
//         assertThat(job.getErrorCode()).isEqualTo("sync-finished");
//         verify(aiJobEventPublisher).publishStatus(4100, response);
//     }

//     @Test
//     @DisplayName("같은 상태를 다시 폴링하면 websocket 이벤트를 중복 발행하지 않는다")
//     void pollSkipsDuplicateEventWhenStateDoesNotChange() {
//         AiAnalysisJob job = AiAnalysisJob.create(4200, 82);
//         ReflectionTestUtils.setField(job, "id", 8200);
//         when(aiAnalysisJobRepository.findById(8200)).thenReturn(Optional.of(job));

//         AiWorkflowStatusResponse response = buildStatusResponse(
//                 8200,
//                 4200,
//                 "RUNNING",
//                 "candidate_ranking",
//                 48,
//                 null
//         );
//         when(fastApiClient.getWorkflowStatus(8200)).thenReturn(response);

//         ReflectionTestUtils.invokeMethod(aiJobMonitor, "poll", 8200, 4200);
//         ReflectionTestUtils.invokeMethod(aiJobMonitor, "poll", 8200, 4200);

//         verify(aiJobEventPublisher).publishStatus(4200, response);
//     }

//     @Test
//     @DisplayName("job row가 없어도 polling 응답이 실패하지 않고 이벤트는 발행한다")
//     void pollPublishesEvenWhenLocalJobRowIsMissing() {
//         when(aiAnalysisJobRepository.findById(8300)).thenReturn(Optional.empty());
//         AiWorkflowStatusResponse response = buildStatusResponse(
//                 8300,
//                 4300,
//                 "FAILED",
//                 "failed",
//                 97,
//                 "preview-error"
//         );
//         when(fastApiClient.getWorkflowStatus(8300)).thenReturn(response);

//         ReflectionTestUtils.invokeMethod(aiJobMonitor, "poll", 8300, 4300);

//         verify(aiJobEventPublisher).publishStatus(4300, response);
//     }

//     private AiWorkflowStatusResponse buildStatusResponse(
//             Integer jobId,
//             Integer projectId,
//             String status,
//             String phase,
//             Integer progress,
//             String errorCode
//     ) {
//         AiWorkflowJobStatusResponse job = new AiWorkflowJobStatusResponse();
//         ReflectionTestUtils.setField(job, "id", jobId);
//         ReflectionTestUtils.setField(job, "projectId", projectId);
//         ReflectionTestUtils.setField(job, "status", status);
//         ReflectionTestUtils.setField(job, "phase", phase);
//         ReflectionTestUtils.setField(job, "progress", progress);
//         ReflectionTestUtils.setField(job, "requestedBy", 99);
//         ReflectionTestUtils.setField(job, "errorCode", errorCode);
//         ReflectionTestUtils.setField(job, "errorMessage", errorCode == null ? null : "detail");

//         AiWorkflowStatusResponse response = new AiWorkflowStatusResponse();
//         ReflectionTestUtils.setField(response, "job", job);
//         return response;
//     }
// }
