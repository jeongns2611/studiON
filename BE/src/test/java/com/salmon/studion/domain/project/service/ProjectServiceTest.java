package com.salmon.studion.domain.project.service;

import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.repository.ProjectRepository;
import com.salmon.studion.global.common.enums.ProjectMode;
import com.salmon.studion.global.common.enums.RootNote;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ProjectServiceTest {

    @Mock private ProjectRepository projectRepository;
    @InjectMocks private ProjectService projectService;

    private static final Integer PROJECT_ID = 1;

    private Project defaultProject() {
        return Project.create("테스트 프로젝트", RootNote.C, ProjectMode.MAJOR, 120.0, 4, 4);
    }

    @Nested
    @DisplayName("changeTempo")
    class ChangeTempoTest {

        @Test
        @DisplayName("tempo가 null이면 INVALID_REQUEST 예외를 던진다")
        void tempoNull() {
            assertThatThrownBy(() -> projectService.changeTempo(PROJECT_ID, null))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.INVALID_REQUEST));

            verifyNoInteractions(projectRepository);
        }

        @Test
        @DisplayName("존재하지 않는 projectId이면 PROJECT_NOT_FOUND 예외를 던진다")
        void projectNotFound() {
            when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> projectService.changeTempo(PROJECT_ID, 150.0))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.PROJECT_NOT_FOUND));
        }

        @Test
        @DisplayName("정상 요청 시 변경된 tempo를 반환하고 엔티티 상태가 갱신된다")
        void success() {
            Project project = defaultProject();
            when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
            when(projectRepository.save(project)).thenReturn(project);

            Double result = projectService.changeTempo(PROJECT_ID, 180.0);

            assertThat(result).isEqualTo(180.0);
            assertThat(project.getTempo()).isEqualTo(180.0);
            verify(projectRepository).save(project);
        }
    }

    @Nested
    @DisplayName("changeKey")
    class ChangeKeyTest {

        @Test
        @DisplayName("rootNote가 null이면 INVALID_REQUEST 예외를 던진다")
        void rootNoteNull() {
            assertThatThrownBy(() -> projectService.changeKey(PROJECT_ID, null, ProjectMode.MINOR))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.INVALID_REQUEST));

            verifyNoInteractions(projectRepository);
        }

        @Test
        @DisplayName("mode가 null이면 INVALID_REQUEST 예외를 던진다")
        void modeNull() {
            assertThatThrownBy(() -> projectService.changeKey(PROJECT_ID, RootNote.G, null))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.INVALID_REQUEST));

            verifyNoInteractions(projectRepository);
        }

        @Test
        @DisplayName("존재하지 않는 projectId이면 PROJECT_NOT_FOUND 예외를 던진다")
        void projectNotFound() {
            when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> projectService.changeKey(PROJECT_ID, RootNote.G, ProjectMode.MINOR))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.PROJECT_NOT_FOUND));
        }

        @Test
        @DisplayName("정상 요청 시 변경된 rootNote와 mode를 가진 Project를 반환한다")
        void success() {
            Project project = defaultProject();
            when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
            when(projectRepository.save(project)).thenReturn(project);

            Project result = projectService.changeKey(PROJECT_ID, RootNote.G, ProjectMode.MINOR);

            assertThat(result.getRootNote()).isEqualTo(RootNote.G);
            assertThat(result.getMode()).isEqualTo(ProjectMode.MINOR);
            verify(projectRepository).save(project);
        }
    }

    @Nested
    @DisplayName("changeTimeSignature")
    class ChangeTimeSignatureTest {

        @Test
        @DisplayName("timeSigNumerator가 null이면 INVALID_REQUEST 예외를 던진다")
        void numeratorNull() {
            assertThatThrownBy(() -> projectService.changeTimeSignature(PROJECT_ID, null, 4))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.INVALID_REQUEST));

            verifyNoInteractions(projectRepository);
        }

        @Test
        @DisplayName("timeSigDenominator가 null이면 INVALID_REQUEST 예외를 던진다")
        void denominatorNull() {
            assertThatThrownBy(() -> projectService.changeTimeSignature(PROJECT_ID, 3, null))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.INVALID_REQUEST));

            verifyNoInteractions(projectRepository);
        }

        @Test
        @DisplayName("존재하지 않는 projectId이면 PROJECT_NOT_FOUND 예외를 던진다")
        void projectNotFound() {
            when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> projectService.changeTimeSignature(PROJECT_ID, 3, 8))
                    .isInstanceOf(BusinessException.class)
                    .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                            .isEqualTo(ErrorCode.PROJECT_NOT_FOUND));
        }

        @Test
        @DisplayName("정상 요청 시 변경된 timeSigNumerator와 timeSigDenominator를 가진 Project를 반환한다")
        void success() {
            Project project = defaultProject();
            when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
            when(projectRepository.save(project)).thenReturn(project);

            Project result = projectService.changeTimeSignature(PROJECT_ID, 3, 8);

            assertThat(result.getTimeSigNumerator()).isEqualTo(3);
            assertThat(result.getTimeSigDenominator()).isEqualTo(8);
            verify(projectRepository).save(project);
        }
    }
}
