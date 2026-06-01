// package com.salmon.studion.domain.ai.service;

// import com.fasterxml.jackson.databind.ObjectMapper;
// import com.salmon.studion.domain.ai.client.FastApiClient;
// import com.salmon.studion.domain.ai.dto.request.AiJobStartApiRequest;
// import com.salmon.studion.domain.ai.dto.request.AiJobStartRequest;
// import com.salmon.studion.domain.ai.dto.request.ProjectEqBandRequest;
// import com.salmon.studion.domain.ai.dto.request.ProjectClipRequest;
// import com.salmon.studion.domain.ai.dto.request.ProjectMasterLimiterRequest;
// import com.salmon.studion.domain.ai.dto.request.ProjectSnapshotRequest;
// import com.salmon.studion.domain.ai.dto.request.ProjectTrackEqRequest;
// import com.salmon.studion.domain.ai.dto.request.ProjectTrackRequest;
// import com.salmon.studion.domain.ai.dto.request.AiUserFeedbackApiRequest;
// import com.salmon.studion.domain.ai.dto.request.AiUserFeedbackRequest;
// import com.salmon.studion.domain.ai.dto.response.AiJobStartResponse;
// import com.salmon.studion.domain.ai.dto.response.AiWorkflowJobResponse;
// import com.salmon.studion.domain.ai.dto.response.AiWorkflowStatusResponse;
// import com.salmon.studion.domain.ai.entity.AiAnalysisJob;
// import com.salmon.studion.domain.ai.monitor.AiJobMonitor;
// import com.salmon.studion.domain.ai.repository.AiAnalysisJobRepository;
// import com.salmon.studion.domain.audio.entity.AudioMetadata;
// import com.salmon.studion.domain.audio.repository.AudioMetadataRepository;
// import com.salmon.studion.domain.eq.service.TrackEqService;
// import com.salmon.studion.domain.limiter.service.MasterLimiterService;
// import com.salmon.studion.domain.project.service.ProjectMemberService;
// import com.salmon.studion.global.common.enums.UserFeedbackType;
// import com.salmon.studion.global.common.response.ErrorCode;
// import com.salmon.studion.global.exception.BusinessException;
// import com.salmon.studion.global.infrastructure.cdn.CdnUrlService;
// import org.junit.jupiter.api.DisplayName;
// import org.junit.jupiter.api.Test;
// import org.junit.jupiter.api.extension.ExtendWith;
// import org.mockito.ArgumentCaptor;
// import org.mockito.InjectMocks;
// import org.mockito.Mock;
// import org.mockito.junit.jupiter.MockitoExtension;
// import org.springframework.test.util.ReflectionTestUtils;

// import java.util.List;
// import java.util.Optional;

// import static org.assertj.core.api.Assertions.assertThat;
// import static org.assertj.core.api.Assertions.assertThatThrownBy;
// import static org.mockito.ArgumentMatchers.any;
// import static org.mockito.Mockito.never;
// import static org.mockito.Mockito.verify;
// import static org.mockito.Mockito.when;

// @ExtendWith(MockitoExtension.class)
// class AiServiceTest {

//     private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

//     @Mock
//     private FastApiClient fastApiClient;

//     @Mock
//     private AiJobMonitor aiJobMonitor;

//     @Mock
//     private AiAnalysisJobRepository aiAnalysisJobRepository;

//     @Mock
//     private AudioMetadataRepository audioMetadataRepository;

//     @Mock
//     private CdnUrlService cdnUrlService;

//     @Mock
//     private ProjectMemberService projectMemberService;

//     @Mock
//     private TrackEqService trackEqService;

//     @Mock
//     private MasterLimiterService masterLimiterService;

//     @InjectMocks
//     private AiService aiService;

//     @Test
//     @DisplayName("startWorkflow는 ai_analysis_job을 먼저 생성한 뒤 DB PK를 FastAPI job_id로 전달한다")
//     void startWorkflowPreCreatesJobAndUsesDatabasePrimaryKey() {
//         AiJobStartApiRequest request = buildStartApiRequest(3001);
//         AiAnalysisJob savedJob = AiAnalysisJob.create(3001, 91);
//         ReflectionTestUtils.setField(savedJob, "id", 7001);

//         when(aiAnalysisJobRepository.save(any(AiAnalysisJob.class))).thenReturn(savedJob);
//         when(audioMetadataRepository.findAllById(List.of(8101))).thenReturn(List.of(
//                 audioMetadata(8101, "audio/test.wav")
//         ));
//         when(cdnUrlService.createAudioUrl("audio/test.wav")).thenReturn("https://cdn.test/audio/test.wav");
//         when(trackEqService.getCurrentTrackEqPayloads(3001, List.of(71))).thenReturn(List.of(
//                 ProjectTrackEqRequest.create(
//                         71,
//                         List.of(ProjectEqBandRequest.create(1, "BELL", 4200, 1.2, -2.5))
//                 )
//         ));
//         when(masterLimiterService.getCurrentMasterLimiterPayload(3001)).thenReturn(
//                 ProjectMasterLimiterRequest.create(true, -6.0, -1.0, 3.0, 80.0, 0.0, 0.0)
//         );
//         when(fastApiClient.startWorkflow(any(AiJobStartRequest.class))).thenReturn(
//                 buildStartResponse(7001, 3001, "start", "accepted", "workflow")
//         );

//         AiJobStartResponse response = aiService.startWorkflow(request, 91);

//         ArgumentCaptor<AiJobStartRequest> requestCaptor = ArgumentCaptor.forClass(AiJobStartRequest.class);
//         verify(fastApiClient).startWorkflow(requestCaptor.capture());
//         verify(aiJobMonitor).startMonitoring(7001, 3001);

//         AiJobStartRequest forwarded = requestCaptor.getValue();
//         assertThat(forwarded.getJobId()).isEqualTo(7001);
//         assertThat(forwarded.getProjectId()).isEqualTo(3001);
//         assertThat(forwarded.getRequestedBy()).isEqualTo(91);
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectTrackRequest().get(0).getTrackId())
//                 .isEqualTo(71);
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectClipRequest().get(0).getClipId())
//                 .isEqualTo(7101);
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectClipRequest().get(0).getAudioUrl())
//                 .isEqualTo("https://cdn.test/audio/test.wav");
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectTrackEqRequest()).hasSize(1);
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectTrackEqRequest().get(0).getTrackId())
//                 .isEqualTo(71);
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectTrackEqRequest().get(0).getBands().get(0).getEqType())
//                 .isEqualTo("BELL");
//         // AI 시작 경로에서는 limiter가 lazy create 되어 snapshot에 포함되어야 한다.
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectMasterLimiterRequest()).isNotNull();
//         assertThat(forwarded.getProjectSnapshotRequest().getProjectMasterLimiterRequest().getIsEnabled()).isTrue();
//         assertThat(response.getJob().getJobId()).isEqualTo(7001);
//     }

//     @Test
//     @DisplayName("startWorkflow는 clip에 audio_url이 이미 있으면 CDN URL로 덮어쓰지 않는다")
//     void startWorkflowKeepsProvidedAudioUrl() {
//         AiJobStartApiRequest request = buildStartApiRequest(3003);
//         ReflectionTestUtils.setField(
//                 request.getProjectSnapshot().getProjectClipRequest().get(0),
//                 "audioUrl",
//                 "https://provided.test/audio.wav"
//         );
//         AiAnalysisJob savedJob = AiAnalysisJob.create(3003, 93);
//         ReflectionTestUtils.setField(savedJob, "id", 7003);

//         when(aiAnalysisJobRepository.save(any(AiAnalysisJob.class))).thenReturn(savedJob);
//         when(trackEqService.getCurrentTrackEqPayloads(3003, List.of(71))).thenReturn(List.of());
//         when(masterLimiterService.getCurrentMasterLimiterPayload(3003)).thenReturn(
//                 ProjectMasterLimiterRequest.create(false, -6.0, -1.0, 3.0, 80.0, 0.0, 0.0)
//         );
//         when(fastApiClient.startWorkflow(any(AiJobStartRequest.class))).thenReturn(
//                 buildStartResponse(7003, 3003, "start", "accepted", "workflow")
//         );

//         aiService.startWorkflow(request, 93);

//         ArgumentCaptor<AiJobStartRequest> requestCaptor = ArgumentCaptor.forClass(AiJobStartRequest.class);
//         verify(fastApiClient).startWorkflow(requestCaptor.capture());
//         verify(audioMetadataRepository, never()).findAllById(any());
//         assertThat(requestCaptor.getValue().getProjectSnapshotRequest().getProjectClipRequest().get(0).getAudioUrl())
//                 .isEqualTo("https://provided.test/audio.wav");
//     }

//     @Test
//     @DisplayName("FastAPI 시작 호출이 실패하면 DB 상태를 FAILED/DISPATCH_FAILED로 남긴다")
//     void startWorkflowMarksDispatchFailedWhenFastApiCallFails() {
//         AiJobStartApiRequest request = buildStartApiRequest(3002);
//         AiAnalysisJob savedJob = AiAnalysisJob.create(3002, 92);
//         ReflectionTestUtils.setField(savedJob, "id", 7002);

//         when(aiAnalysisJobRepository.save(any(AiAnalysisJob.class))).thenReturn(savedJob);
//         when(audioMetadataRepository.findAllById(List.of(8101))).thenReturn(List.of(
//                 audioMetadata(8101, "audio/test.wav")
//         ));
//         when(cdnUrlService.createAudioUrl("audio/test.wav")).thenReturn("https://cdn.test/audio/test.wav");
//         when(trackEqService.getCurrentTrackEqPayloads(3002, List.of(71))).thenReturn(List.of());
//         when(masterLimiterService.getCurrentMasterLimiterPayload(3002)).thenReturn(
//                 ProjectMasterLimiterRequest.create(false, -6.0, -1.0, 3.0, 80.0, 0.0, 0.0)
//         );
//         when(fastApiClient.startWorkflow(any(AiJobStartRequest.class)))
//                 .thenThrow(new BusinessException(ErrorCode.AI_FASTAPI_CALL_FAILED, "downstream failed"));

//         assertThatThrownBy(() -> aiService.startWorkflow(request, 92))
//                 .isInstanceOf(BusinessException.class)
//                 .extracting(exception -> ((BusinessException) exception).getErrorCode())
//                 .isEqualTo(ErrorCode.AI_FASTAPI_CALL_FAILED);

//         verify(aiJobMonitor, never()).startMonitoring(7002, 3002);
//         assertThat(savedJob.getStatus()).isEqualTo("FAILED");
//         assertThat(savedJob.getPhase()).isEqualTo("DISPATCH_FAILED");
//         assertThat(savedJob.getErrorCode()).isEqualTo(ErrorCode.AI_FASTAPI_CALL_FAILED.getCode());
//     }

//     @Test
//     @DisplayName("프로젝트 멤버는 job 상태 조회를 할 수 있다")
//     void getWorkflowStatusAllowsProjectMember() {
//         AiAnalysisJob savedJob = AiAnalysisJob.create(3010, 51);
//         ReflectionTestUtils.setField(savedJob, "id", 7010);
//         when(aiAnalysisJobRepository.findById(7010)).thenReturn(Optional.of(savedJob));
//         when(fastApiClient.getWorkflowStatus(7010)).thenReturn(new AiWorkflowStatusResponse());

//         aiService.getWorkflowStatus(7010, 51);

//         verify(projectMemberService).validateProjectMember(3010, 51);
//         verify(fastApiClient).getWorkflowStatus(7010);
//     }

//     @Test
//     @DisplayName("존재하지 않는 jobId 조회는 AI_JOB_NOT_FOUND를 반환한다")
//     void getWorkflowStatusThrowsWhenJobDoesNotExist() {
//         when(aiAnalysisJobRepository.findById(7099)).thenReturn(Optional.empty());

//         assertThatThrownBy(() -> aiService.getWorkflowStatus(7099, 11))
//                 .isInstanceOf(BusinessException.class)
//                 .extracting(exception -> ((BusinessException) exception).getErrorCode())
//                 .isEqualTo(ErrorCode.AI_JOB_NOT_FOUND);
//     }

//     @Test
//     @DisplayName("feedback 요청의 project_id가 job 소속 프로젝트와 다르면 INVALID_REQUEST를 반환한다")
//     void dispatchUserFeedbackRejectsProjectMismatch() {
//         AiAnalysisJob savedJob = AiAnalysisJob.create(3020, 52);
//         ReflectionTestUtils.setField(savedJob, "id", 7020);
//         when(aiAnalysisJobRepository.findById(7020)).thenReturn(Optional.of(savedJob));

//         AiUserFeedbackApiRequest request = buildFeedbackApiRequest(9999, UserFeedbackType.RESUME);

//         assertThatThrownBy(() -> aiService.dispatchUserFeedback(7020, request, 52))
//                 .isInstanceOf(BusinessException.class)
//                 .extracting(exception -> ((BusinessException) exception).getErrorCode())
//                 .isEqualTo(ErrorCode.INVALID_REQUEST);
//     }

//     @Test
//     @DisplayName("멤버가 일치하는 feedback 요청을 보내면 path jobId 기준으로 FastAPI에 전달한다")
//     void dispatchUserFeedbackUsesPathJobId() {
//         AiAnalysisJob savedJob = AiAnalysisJob.create(3030, 53);
//         ReflectionTestUtils.setField(savedJob, "id", 7030);
//         when(aiAnalysisJobRepository.findById(7030)).thenReturn(Optional.of(savedJob));
//         when(fastApiClient.dispatchUserFeedback(any(AiUserFeedbackRequest.class))).thenReturn(
//                 buildJobResponse(7030, 3030, "resume_plan_input", "accepted", "workflow")
//         );

//         AiUserFeedbackApiRequest request = buildFeedbackApiRequest(3030, UserFeedbackType.RESUME);
//         aiService.dispatchUserFeedback(7030, request, 53);

//         ArgumentCaptor<AiUserFeedbackRequest> requestCaptor = ArgumentCaptor.forClass(AiUserFeedbackRequest.class);
//         verify(fastApiClient).dispatchUserFeedback(requestCaptor.capture());
//         AiUserFeedbackRequest forwarded = requestCaptor.getValue();
//         assertThat(forwarded.getJobId()).isEqualTo(7030);
//         assertThat(forwarded.getProjectId()).isEqualTo(3030);
//         assertThat(forwarded.getIssueId()).isEqualTo("issue-17");
//         assertThat(forwarded.getActionType()).isEqualTo("apply_master_gain_trim");
//         assertThat(forwarded.getActionPayload().path("recommendedReductionDb").asDouble())
//                 .isEqualTo(1.5);
//         assertThat(forwarded.getUserDecision()).isEqualTo(UserFeedbackType.RESUME);
//     }

//     @Test
//     @DisplayName("인증 사용자가 없으면 UNAUTHORIZED를 반환한다")
//     void requiresAuthenticatedUser() {
//         assertThatThrownBy(() -> aiService.startWorkflow(buildStartApiRequest(3040), null))
//                 .isInstanceOf(BusinessException.class)
//                 .extracting(exception -> ((BusinessException) exception).getErrorCode())
//                 .isEqualTo(ErrorCode.UNAUTHORIZED);
//     }

//     private AiJobStartApiRequest buildStartApiRequest(Integer projectId) {
//         AiJobStartApiRequest request = new AiJobStartApiRequest();
//         ReflectionTestUtils.setField(request, "projectId", projectId);
//         ReflectionTestUtils.setField(request, "issueTypes", List.of("band_overlap"));
//         ReflectionTestUtils.setField(request, "validatorMode", "PASS");
//         ReflectionTestUtils.setField(request, "criticMode", "PASS");
//         ReflectionTestUtils.setField(request, "projectSnapshot", buildProjectSnapshotRequest());
//         return request;
//     }

//     private AiUserFeedbackApiRequest buildFeedbackApiRequest(Integer projectId, UserFeedbackType decision) {
//         AiUserFeedbackApiRequest request = new AiUserFeedbackApiRequest();
//         ReflectionTestUtils.setField(request, "projectId", projectId);
//         ReflectionTestUtils.setField(request, "issueId", "issue-17");
//         ReflectionTestUtils.setField(request, "actionType", "apply_master_gain_trim");
//         ReflectionTestUtils.setField(
//                 request,
//                 "actionPayload",
//                 OBJECT_MAPPER.createObjectNode().put("recommendedReductionDb", 1.5)
//         );
//         ReflectionTestUtils.setField(request, "selectedRegionId", 17);
//         ReflectionTestUtils.setField(request, "preserveClipId", 23);
//         ReflectionTestUtils.setField(request, "userFeedbackMessage", "keep the kick");
//         ReflectionTestUtils.setField(request, "userDecision", decision);
//         return request;
//     }

//     private AiJobStartResponse buildStartResponse(
//             Integer jobId,
//             Integer projectId,
//             String dispatchType,
//             String status,
//             String queueName
//     ) {
//         AiJobStartResponse response = new AiJobStartResponse();
//         ReflectionTestUtils.setField(
//                 response,
//                 "job",
//                 buildJobResponse(jobId, projectId, dispatchType, status, queueName)
//         );
//         return response;
//     }

//     private AiWorkflowJobResponse buildJobResponse(
//             Integer jobId,
//             Integer projectId,
//             String dispatchType,
//             String status,
//             String queueName
//     ) {
//         AiWorkflowJobResponse response = new AiWorkflowJobResponse();
//         ReflectionTestUtils.setField(response, "jobId", jobId);
//         ReflectionTestUtils.setField(response, "projectId", projectId);
//         ReflectionTestUtils.setField(response, "dispatchType", dispatchType);
//         ReflectionTestUtils.setField(response, "status", status);
//         ReflectionTestUtils.setField(response, "queueName", queueName);
//         return response;
//     }

//     private ProjectSnapshotRequest buildProjectSnapshotRequest() {
//         ProjectTrackRequest track = new ProjectTrackRequest();
//         ReflectionTestUtils.setField(track, "trackId", 71);
//         ReflectionTestUtils.setField(track, "name", "Track 71");

//         ProjectClipRequest clip = new ProjectClipRequest();
//         ReflectionTestUtils.setField(clip, "clipId", 7101);
//         ReflectionTestUtils.setField(clip, "trackId", 71);
//         ReflectionTestUtils.setField(clip, "startMs", 0);
//         ReflectionTestUtils.setField(clip, "endMs", 2400);
//         ReflectionTestUtils.setField(clip, "audioMetadataId", 8101);
//         ReflectionTestUtils.setField(clip, "audioStartMs", 0);
//         ReflectionTestUtils.setField(clip, "audioDurationMs", 2400);

//         ProjectSnapshotRequest snapshot = new ProjectSnapshotRequest();
//         ReflectionTestUtils.setField(snapshot, "durationMs", 2400);
//         ReflectionTestUtils.setField(snapshot, "bpm", 120);
//         ReflectionTestUtils.setField(snapshot, "numerator", 4);
//         ReflectionTestUtils.setField(snapshot, "denominator", 4);
//         ReflectionTestUtils.setField(snapshot, "projectTrackRequest", List.of(track));
//         ReflectionTestUtils.setField(snapshot, "projectClipRequest", List.of(clip));
//         return snapshot;
//     }

//     private AudioMetadata audioMetadata(Integer id, String objectKey) {
//         AudioMetadata metadata = AudioMetadata.create(
//                 objectKey,
//                 "original.wav",
//                 "stored.wav",
//                 null,
//                 1234,
//                 2400
//         );
//         ReflectionTestUtils.setField(metadata, "id", id);
//         return metadata;
//     }
// }
