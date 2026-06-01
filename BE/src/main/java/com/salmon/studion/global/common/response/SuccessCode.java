package com.salmon.studion.global.common.response;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum SuccessCode {

    // 공통       COMMON_000
    SUCCESS(HttpStatus.OK, "COMMON_200", "요청에 성공했습니다."),
    CREATED(HttpStatus.CREATED, "COMMON_201", "생성에 성공했습니다."),
    UPDATED(HttpStatus.OK, "COMMON_202", "수정에 성공했습니다."),
    DELETED(HttpStatus.OK, "COMMON_204", "삭제에 성공했습니다."),

    // 유저 U_000
    USER_FOUND(HttpStatus.OK, "U_001", "사용자 조회에 성공했습니다."),
    USER_UPDATED(HttpStatus.OK, "U_002", "사용자 정보 수정에 성공했습니다."),

    // 프로젝트 P_000
    PROJECT_CREATED(HttpStatus.CREATED, "P_001", "프로젝트 생성에 성공했습니다."),
    PROJECT_FOUND(HttpStatus.OK, "P_002", "프로젝트 조회에 성공했습니다."),
    PROJECT_LIST_FOUND(HttpStatus.OK, "P_003", "프로젝트 목록 조회에 성공했습니다."),
    PROJECT_UPDATED(HttpStatus.OK, "P_004", "프로젝트 수정에 성공했습니다."),
    PROJECT_DELETED(HttpStatus.OK, "P_005", "프로젝트 삭제에 성공했습니다."),
    PROJECT_JOINED(HttpStatus.OK, "P_006", "프로젝트 참여에 성공했습니다."),

    // 트랙 T_000
    TRACK_CREATED(HttpStatus.CREATED, "T_001", "트랙 생성에 성공했습니다."),
    TRACK_FOUND(HttpStatus.OK, "T_002", "트랙 조회에 성공했습니다."),
    TRACK_LIST_FOUND(HttpStatus.OK, "T_003", "트랙 목록 조회에 성공했습니다."),
    TRACK_UPDATED(HttpStatus.OK, "T_004", "트랙 수정에 성공했습니다."),
    TRACK_DELETED(HttpStatus.OK, "T_005", "트랙 삭제에 성공했습니다."),

    // 오디오 A_000
    AUDIO_UPLOADED(HttpStatus.CREATED, "A_001", "오디오 업로드에 성공했습니다."),
    AUDIO_FOUND(HttpStatus.OK, "A_002", "오디오 조회에 성공했습니다."),
    AUDIO_LIST_FOUND(HttpStatus.OK, "A_003", "오디오 목록 조회에 성공했습니다."),
    AUDIO_DELETED(HttpStatus.OK, "A_004", "오디오 삭제에 성공했습니다."),
    AUDIO_EXPORT_CREATED(HttpStatus.CREATED, "A_005", "오디오 내보내기에 성공했습니다."),

    // 코멘트 C_000
    COMMENT_CREATED(HttpStatus.CREATED, "C_001", "댓글 생성에 성공했습니다."),
    COMMENT_FOUND(HttpStatus.OK, "C_002", "댓글 조회에 성공했습니다."),
    COMMENT_LIST_FOUND(HttpStatus.OK, "C_003", "댓글 목록 조회에 성공했습니다."),
    COMMENT_UPDATED(HttpStatus.OK, "C_004", "댓글 수정에 성공했습니다."),
    COMMENT_DELETED(HttpStatus.OK, "C_005", "댓글 삭제에 성공했습니다."),
    COMMENT_RESOLVED(HttpStatus.OK, "C_006", "댓글 해결 처리에 성공했습니다."),

    // EQ EQ_000
    EQ_UPDATED(HttpStatus.OK, "EQ_001", "EQ 변경에 성공했습니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;
}
