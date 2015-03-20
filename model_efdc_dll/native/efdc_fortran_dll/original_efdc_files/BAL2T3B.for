      SUBROUTINE BAL2T3B(IBALSTDT)  
C  
C CHANGE RECORD  
C  SUBROUTINE ADDED FOR 2 TIME-LEVEL BALANCES INCLUDING SED,SND,TOX  
C  MODIFIED SND MASS BALANCE WITH RESPECT TO BED LOAD OUTFLOW  
C  ADDED QDWASTE TO WATER MASS BALANCE  
C **  SUBROUTINES CALBAL CALCULATE GLOBAL VOLUME, MASS, MOMENTUM,  
C **  AND ENERGY BALANCES  
C  
      USE GLOBAL  
 	IMPLICIT NONE
	INTEGER::LUTMP,LDTMP,L,K,NSX,NSB,IBALSTDT,NT,M  
        INTEGER::LF,LL,ithds
      IF(ISDYNSTP.EQ.0)THEN  
        DELT=DT  
      ELSE  
        DELT=DTDYN  
      END IF  
C  
C **  ACCUMULATE INTERNAL SOURCES AND SINKS  
C  
      IF(IBALSTDT.EQ.1)THEN  
!$OMP PARALLEL DO PRIVATE(LF,LL) REDUCTION(-:WVOLOUT)
!$OMP&  REDUCTION(+:BVOLOUT,VOLMORPH2T)
      do ithds=0,nthds-1
         LF=jse(1,ithds)
         LL=jse(2,ithds)
c
        DO L=LF,LL
          WVOLOUT=WVOLOUT-DTSED*QMORPH(L)  
          BVOLOUT=BVOLOUT+DTSED*QMORPH(L)
          VOLMORPH2T=VOLMORPH2T+DTSED*QMORPH(L)
        ENDDO  
c
      enddo
      ENDIF  
      IF(ISTRAN(5).GE.1)THEN  
        DO NT=1,NTOX  
          M=MSVTOX(NT)  
      WRITE(8,*)'NT M ',NT,M  
!$OMP PARALLEL DO PRIVATE(LF,LL)
      do ithds=0,nthds-1
         LF=jse_2_LC(1,ithds)
         LL=jse_2_LC(2,ithds)
c
          DO K=1,KC  
            DO L=LF,LL
              CONT(L,K)=TOX(L,K,NT)  
            ENDDO  
          ENDDO  
c
      enddo
C  
C  TOXBLB2T(NT) IS NET TOXIC MASS GOING OUT OF DOMAIN DUE  
C  DUE TO BED LOAD TRANSPORT OUT OF DOMAIN  
C  
          IF(IBALSTDT.EQ.1)THEN  
            IF(NSBDLDBC.GT.0) THEN  
              TOXBLB2T(NT)=TOXBLB2T(NT)+DTSED*TOXBLB(NT)  
            ENDIF  
C  
C  TOXFLUXW2T(NT) IS WATER COLUMN SIDE TOXIC FLUX DUE TO SUSPENDED LOAD  
C    (POSITIVE INTO WATER COLUMN)  
C  TOXFLUXB2T(NT) IS BED SIDE TOXIC FLUX DUE TO SUSPENDED LOAD (POSITIVE  
C  TADFLUX2T(NT) IS PORE WATER ADVECTION+DIFFUSION FLUX (POSITIVE INTO W  
C  TOXFBL2T(NT) IS NET TOXIC FLUX FROM BED ASSOCIATED WITH BED LOAD TRAN  
C    (SHOULD EQUAL TOXBLB2T(NT)  
C  
            DO L=2,LA  
              TOXFLUXW2T(NT)=TOXFLUXW2T(NT)+DTSED*DXYP(L)*TOXF(L,0,NT)  
              TOXFLUXB2T(NT)=TOXFLUXB2T(NT)+DTSED*DXYP(L)*TOXFB(L,
     &            KBT(L),NT)  
              TADFLUX2T(NT)=TADFLUX2T(NT)+DTSED*DXYP(L)*TADFLUX(L,NT)  
            ENDDO  
            TOXFBL2T(NT)=TOXFBL2T(NT)+DTSED*TOXFBLT(NT)  
          ENDIF  
        ENDDO  
      ENDIF  
      IF(ISTRAN(6).GE.1)THEN  
        DO NSX=1,NSED  
          M=MSVSED(NSX)  
!$OMP PARALLEL DO PRIVATE(LF,LL)
      do ithds=0,nthds-1
         LF=jse_2_LC(1,ithds)
         LL=jse_2_LC(2,ithds)
c
          DO K=1,KC  
            DO L=LF,LL
              CONT(L,K)=SED(L,K,NSX)  
            ENDDO  
          ENDDO  
c
      enddo
C  
C SEDFLUX2T(NSX) IS IS NET COHESIVE MASS FLUX POSITIVE FROM BED  
C   TO WATER COLUMN  
C  
          IF(IBALSTDT.EQ.1)THEN  
            DO L=2,LA  
              SEDFLUX2T(NSX)=SEDFLUX2T(NSX)+DTSED*DXYP(L)*SEDF(L,0,NSX)  
            ENDDO  
          ENDIF  
        ENDDO  
      ENDIF  
      IF(ISTRAN(7).GE.1)THEN  
        DO NSX=1,NSND  
          M=MSVSND(NSX)  
!$OMP PARALLEL DO PRIVATE(LF,LL)
      do ithds=0,nthds-1
         LF=jse_2_LC(1,ithds)
         LL=jse_2_LC(2,ithds)
c
          DO K=1,KC  
            DO L=LF,LL
              CONT(L,K)=SND(L,K,NSX)  
            ENDDO  
          ENDDO  
c
      enddo
C  
C  SBLOUT2T(NSX) IS NET NONCOHESIVE SEDIMENT MASS GOING OUT OF DOMAIN DU  
C  DUE TO BED LOAD TRANSPORT OUT OF DOMAIN  
C  
          IF(IBALSTDT.EQ.1)THEN  
            IF(NSBDLDBC.GT.0) THEN  
              DO NSB=1,NSBDLDBC  
                LUTMP=LSBLBCU(NSB)  
                LDTMP=LSBLBCD(NSB)  
                IF(LDTMP.EQ.0) THEN  
                  SBLOUT2T(NSX)=SBLOUT2T(NSX)+  
     &                DTSED*QSBDLDOT(LUTMP,NSX)  
                ENDIF  
              ENDDO  
            ENDIF  
          ENDIF  
C  
C  SNDFLUX2T(NSX) IS NET NONCOHESIVE SEDIMENT FLUX DUE TO SUSPENDED LOAD  
C    (POSITIVE INTO WATER COLUMN)  
C  SNDFBL2T(NSX) IS NET NONCOHESIVE SEDIMENT FLUX FROM BED ASSOCIATED WI  
C    BED LOAD TRANSPORT (SHOULD EQUAL SBLOUT2T(NSX))  
C  
          IF(IBALSTDT.EQ.1)THEN  
            DO L=2,LA  
              SNDFLUX2T(NSX)=SNDFLUX2T(NSX)+DTSED*DXYP(L)*(SNDF(L,0,NSX)  
     &            -SNDFBL(L,NSX))  
              SNDFBL2T(NSX)=SNDFBL2T(NSX)+DTSED*DXYP(L)*SNDFBL(L,NSX)  
            ENDDO  
          ENDIF  
        ENDDO  
      ENDIF  
  800 FORMAT('N,NS,SNDFBL2T,DEL',2I5,2E14.5)  
      RETURN  
      END  

