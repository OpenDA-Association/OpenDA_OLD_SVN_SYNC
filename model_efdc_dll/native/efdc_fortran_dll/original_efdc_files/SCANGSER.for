      SUBROUTINE SCANGSER
      USE GLOBAL
      CHARACTER*80 SKIP
      CHARACTER*11 INFILE

      WRITE(*,'(A)')'SCANNING INPUT FILE: GATESER.INP'
      INFILE='GATESER.INP'

      OPEN(1,FILE='GATESER.INP',STATUS='UNKNOWN')  
      ! *** FIND THE MAXIMUM NUMBER OF TABLE DATA POINTS  
      NDQCLT=0  
      DO IS=1,22
        READ(1,10)SKIP  
        !WRITE(7,'(A,1X,A)')CARD,SKIP(1:LEN_TRIM(SKIP))  
      ENDDO  
      DO NS=1,NQCTLT
        READ(1,*,IOSTAT=ISO)ISTYP,M
        NDQCLT=MAX(NDQCLT,M)  
        IF(ISO.GT.0)GOTO 20  
        DO M=1,M
          READ(1,10)SKIP  
          !WRITE(7,'(A,1X,A)')CARD,SKIP(1:LEN_TRIM(SKIP))  
        ENDDO  
      ENDDO  
      CLOSE(1)  
      NDQCLT2=NDQCLT  
      RETURN

   10 FORMAT(A80)   
   20 WRITE(*,30)INFILE
      WRITE(8,30)INFILE
   30 FORMAT(' READ ERROR IN FILE: ',A10)
      STOP

      END