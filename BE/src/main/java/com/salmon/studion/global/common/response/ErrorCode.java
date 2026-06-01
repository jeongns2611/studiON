package com.salmon.studion.global.common.response;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum ErrorCode {

    // 공통 COMMON_000
    FAIL(HttpStatus.BAD_REQUEST, "COMMON_400", "요청이 실패했습니다."),
    INVALID_REQUEST(HttpStatus.BAD_REQUEST, "COMMON_001", "잘못된 요청입니다."),
    INVALID_INPUT_VALUE(HttpStatus.BAD_REQUEST, "COMMON_002", "입력값이 올바르지 않습니다."),
    METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "COMMON_003", "지원하지 않는 HTTP 메서드입니다."),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "COMMON_500", "서버 내부 오류가 발생했습니다."),
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "COMMON_401", "인증이 필요합니다."),
    FORBIDDEN(HttpStatus.FORBIDDEN, "COMMON_403", "접근 권한이 없습니다."),
    NOT_FOUND(HttpStatus.NOT_FOUND, "COMMON_404", "요청한 리소스를 찾을 수 없습니다."),

    // 유저 U_000
    USER_NOT_FOUND(HttpStatus.NOT_FOUND, "U_001", "사용자를 찾을 수 없습니다."),
    USER_ALREADY_EXISTS(HttpStatus.CONFLICT, "U_002", "이미 존재하는 사용자입니다."),
    INVALID_USER_ROLE(HttpStatus.BAD_REQUEST, "U_003", "올바르지 않은 사용자 권한입니다."),

    // 프로젝트 P_000
    PROJECT_NOT_FOUND(HttpStatus.NOT_FOUND, "P_001", "프로젝트를 찾을 수 없습니다."),
    PROJECT_ACCESS_DENIED(HttpStatus.FORBIDDEN, "P_002", "프로젝트 접근 권한이 없습니다."),
    PROJECT_MEMBER_NOT_FOUND(HttpStatus.NOT_FOUND, "P_003", "프로젝트 멤버를 찾을 수 없습니다."),
    PROJECT_INVITE_CODE_INVALID(HttpStatus.BAD_REQUEST, "P_004", "유효하지 않은 초대 코드입니다."),
    PROJECT_INVITE_CODE_EXPIRED(HttpStatus.BAD_REQUEST, "P_005", "만료된 초대 코드입니다."),
    PROJECT_MEMBER_ALREADY_EXISTS(HttpStatus.CONFLICT, "P_006", "이미 프로젝트 멤버입니다."),
    PROJECT_INVITE_CODE_GENERATION_FAILED(HttpStatus.INTERNAL_SERVER_ERROR,"P_007","고유한 프로젝트 초대코드를 생성하지 못했습니다."),
    PROJECT_SAVE_IN_PROGRESS(HttpStatus.CONFLICT, "P_008", "이미 프로젝트 저장이 진행 중입니다."),

    // 트랙 T_000
    TRACK_NOT_FOUND(HttpStatus.NOT_FOUND, "T_001", "트랙을 찾을 수 없습니다."),
    TRACK_ACCESS_DENIED(HttpStatus.FORBIDDEN, "T_002", "트랙 접근 권한이 없습니다."),
    TRACK_LOCKED(HttpStatus.CONFLICT, "T_003", "다른 사용자가 트랙을 작업 중입니다."),
    TRACK_LIMIT_EXCEEDED(HttpStatus.BAD_REQUEST, "T_004", "트랙은 최대 50개까지 생성할 수 있습니다."),

    // 오디오 A_000
    AUDIO_NOT_FOUND(HttpStatus.NOT_FOUND, "A_001", "오디오 파일을 찾을 수 없습니다."),
    AUDIO_UPLOAD_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "A_002", "오디오 업로드에 실패했습니다."),
    AUDIO_DOWNLOAD_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "A_003", "오디오 다운로드에 실패했습니다."),
    AUDIO_INVALID_FORMAT(HttpStatus.BAD_REQUEST, "A_004", "지원하지 않는 오디오 형식입니다."),
    AUDIO_FILE_TOO_LARGE(HttpStatus.BAD_REQUEST, "A_005", "오디오 파일 크기가 너무 큽니다."),
    AUDIO_INVALID_FILE_NAME(HttpStatus.BAD_REQUEST, "A_006", "오디오 파일명 또는 확장자가 올바르지 않습니다."),
    AUDIO_FILE_NOT_FOUND(HttpStatus.NOT_FOUND, "A_007", "업로드한 오디오 파일을 찾을 수 없습니다."),
    AUDIO_FILE_SIZE_MISMATCH(HttpStatus.BAD_REQUEST, "A_008", "업로드한 오디오 파일 크기가 요청 정보와 일치하지 않습니다."),
    AUDIO_CONTENT_TYPE_MISMATCH(HttpStatus.BAD_REQUEST, "A_009", "업로드한 오디오 파일 타입이 요청 정보와 일치하지 않습니다."),
    S3_OBJECT_VALIDATE_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "A_010", "S3 오디오 파일 검증 중 오류가 발생했습니다."),
    AUDIO_INVALID_PROJECT_SCOPE(HttpStatus.BAD_REQUEST, "A_011", "오디오 파일의 프로젝트 정보가 올바르지 않습니다."),
    AUDIO_OBJECT_KEY_MISMATCH(HttpStatus.BAD_REQUEST, "A_012", "오디오 파일 참조 정보가 올바르지 않습니다."),
    AUDIO_METADATA_NOT_FOUND(HttpStatus.NOT_FOUND, "A_013", "오디오 메타데이터를 찾을 수 없습니다."),
    AUDIO_VERSION_NOT_FOUND(HttpStatus.NOT_FOUND, "A_014", "해당 오디오 버전 정보를 찾을 수 없습니다."),

    // 코멘트 C_000
    COMMENT_NOT_FOUND(HttpStatus.NOT_FOUND, "C_001", "댓글을 찾을 수 없습니다."),
    COMMENT_ACCESS_DENIED(HttpStatus.FORBIDDEN, "C_002", "댓글 접근 권한이 없습니다."),
    COMMENT_ALREADY_RESOLVED(HttpStatus.CONFLICT, "C_003", "이미 해결된 댓글입니다."),

    // 클립 CL_000
    CLIP_NOT_FOUND(HttpStatus.NOT_FOUND, "CL_001", "클립을 찾을 수 없습니다."),
    CLIP_LOCKED(HttpStatus.CONFLICT, "CL_002", "다른 사용자가 편집 중인 클립입니다."),
    CLIP_OVERLAP(HttpStatus.CONFLICT, "CL_003", "해당 위치에 클립이 이미 존재합니다."),
    CLIP_BAR_LIMIT_EXCEEDED(HttpStatus.BAD_REQUEST, "CL_004", "클립이 최대 마디(200)를 초과합니다."),

    // AI AI_000
    AI_FASTAPI_CALL_FAILED(HttpStatus.BAD_GATEWAY, "AI_001", "AI 서버 호출에 실패했습니다."),
    AI_FASTAPI_TIMEOUT(HttpStatus.GATEWAY_TIMEOUT, "AI_002", "AI 서버 작업 대기 시간이 초과되었습니다."),
    AI_JOB_ALREADY_EXISTS(HttpStatus.CONFLICT, "AI_003", "이미 존재하는 AI job 입니다."),
    AI_JOB_NOT_FOUND(HttpStatus.NOT_FOUND, "AI_004", "AI job을 찾을 수 없습니다."),
    AI_INVALID_RESPONSE(HttpStatus.BAD_GATEWAY, "AI_005", "AI 서버 응답 형식이 올바르지 않습니다."),

    // EQ EQ_000
    TRACK_EQ_NOT_FOUND(HttpStatus.NOT_FOUND, "EQ_001", "해당 track eq를 찾을 수 없습니다."),
    TRACK_EQ_LOCKED(HttpStatus.CONFLICT, "EQ_002", "다른 사용자가 EQ를 편집 중입니다."),

    // LIMITER LM_000
    MASTER_LIMITER_NOT_FOUND(HttpStatus.NOT_FOUND, "LM_001", "마스터 리미터를 찾을 수 없습니다."),
    MASTER_LIMITER_LOCKED(HttpStatus.CONFLICT, "LM_002", "다른 사용자가 리미터를 편집 중입니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;
}
